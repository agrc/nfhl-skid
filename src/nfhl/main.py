#!/usr/bin/env python
# * coding: utf8 *
"""
Run the nfhl-skid script as a cloud function.
"""
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import arcgis
from palletjack import extract, load, transform, utils
from supervisor.message_handlers import SendGridHandler
from supervisor.models import MessageDetails, Supervisor

#: This makes it work when calling with just `python <file>`/installing via pip and in the gcf framework, where
#: the relative imports fail because of how it's calling the function.
try:
    from . import config, version
except ImportError:
    import config
    import version


def _get_secrets():
    """A helper method for loading secrets from either a GCF mount point or the local src/nfhl-skid/secrets/secrets.
    json file

    Raises:
        FileNotFoundError: If the secrets file can't be found.

    Returns:
        dict: The secrets .json loaded as a dictionary
    """

    secret_folder = Path("/secrets")

    #: Try to get the secrets from the Cloud Function mount point
    if secret_folder.exists():
        return json.loads(Path("/secrets/app/secrets.json").read_text(encoding="utf-8"))

    #: Otherwise, try to load a local copy for local development
    secret_folder = Path(__file__).parent / "secrets"
    if secret_folder.exists():
        return json.loads((secret_folder / "secrets.json").read_text(encoding="utf-8"))

    raise FileNotFoundError("Secrets folder not found; secrets not loaded.")


def _initialize(log_path, sendgrid_api_key):
    """A helper method to set up logging and supervisor

    Args:
        log_path (Path): File path for the logfile to be written
        sendgrid_api_key (str): The API key for sendgrid for this particular application

    Returns:
        Supervisor: The supervisor object used for sending messages
    """

    skid_logger = logging.getLogger(config.SKID_NAME)
    skid_logger.setLevel(config.LOG_LEVEL)
    palletjack_logger = logging.getLogger("palletjack")
    palletjack_logger.setLevel(config.LOG_LEVEL)

    cli_handler = logging.StreamHandler(sys.stdout)
    cli_handler.setLevel(config.LOG_LEVEL)
    formatter = logging.Formatter(
        fmt="%(levelname)-7s %(asctime)s %(name)15s:%(lineno)5s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    cli_handler.setFormatter(formatter)

    log_handler = logging.FileHandler(log_path, mode="w")
    log_handler.setLevel(config.LOG_LEVEL)
    log_handler.setFormatter(formatter)

    skid_logger.addHandler(cli_handler)
    skid_logger.addHandler(log_handler)
    palletjack_logger.addHandler(cli_handler)
    palletjack_logger.addHandler(log_handler)

    #: Log any warnings at logging.WARNING
    #: Put after everything else to prevent creating a duplicate, default formatter
    #: (all log messages were duplicated if put at beginning)
    logging.captureWarnings(True)

    skid_logger.debug("Creating Supervisor object")
    skid_supervisor = Supervisor(handle_errors=False)
    sendgrid_settings = config.SENDGRID_SETTINGS
    sendgrid_settings["api_key"] = sendgrid_api_key
    skid_supervisor.add_message_handler(
        SendGridHandler(
            sendgrid_settings=sendgrid_settings, client_name=config.SKID_NAME, client_version=version.__version__
        )
    )

    return skid_supervisor


def _remove_log_file_handlers(log_name, loggers):
    """A helper function to remove the file handlers so the tempdir will close correctly

    Args:
        log_name (str): The logfiles filename
        loggers (List<str>): The loggers that are writing to log_name
    """

    for logger in loggers:
        for handler in logger.handlers:
            try:
                if log_name in handler.stream.name:
                    logger.removeHandler(handler)
                    handler.close()
            except Exception:
                pass


def _hazard_areas(hazard_areas_df):
    #: Calculate label values for symbology
    one_per_annual_flood_dq = (hazard_areas_df["FLD_ZONE"].isin(["A", "AE", "AH", "AO", "VE"])) & (
        hazard_areas_df["ZONE_SUBTY"].isnull()
    )
    regulatory_floodway_dq = (hazard_areas_df["FLD_ZONE"] == "AE") & (
        hazard_areas_df["ZONE_SUBTY"].isin(["FLOODWAY", "FLOODWAY CONTAINED IN CHANNEL"])
    )
    undet_flood_hazard_dq = hazard_areas_df["FLD_ZONE"] == "D"
    point_oh_two_percent_annual_flood_dq = (hazard_areas_df["FLD_ZONE"] == "X") & (
        hazard_areas_df["ZONE_SUBTY"].isin(
            [
                "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
                "1 PCT DEPTH LESS THAN 1 FOOT",
                "1 PCT DRAINAGE AREA LESS THAN 1 SQUARE MILE",
            ]
        )
    )
    reduced_risk_levee_dq = (hazard_areas_df["FLD_ZONE"] == "X") & (
        hazard_areas_df["ZONE_SUBTY"] == "AREA WITH REDUCED FLOOD RISK DUE TO LEVEE"
    )
    area_not_included_dq = hazard_areas_df["FLD_ZONE"] == "AREA NOT INCLUDED"

    hazard_areas_df["label"] = ""
    hazard_areas_df.loc[one_per_annual_flood_dq, "label"] = "1% Annual Chance Flood Hazard"
    hazard_areas_df.loc[regulatory_floodway_dq, "label"] = "Regulatory Floodway"
    hazard_areas_df.loc[undet_flood_hazard_dq, "label"] = "Area of Undetermined Flood Hazard"
    hazard_areas_df.loc[point_oh_two_percent_annual_flood_dq, "label"] = "0.2% Annual Chance Flood Hazard"
    hazard_areas_df.loc[reduced_risk_levee_dq, "label"] = "Area with Reduced Flood Risk due to Levee"
    hazard_areas_df.loc[area_not_included_dq, "label"] = "Area Not Included"

    #: fill null strings with empty string '' to fix featureset error
    for col in hazard_areas_df.columns:
        if hazard_areas_df[col].dtype == "string":
            hazard_areas_df[col].fillna("", inplace=True)

    return hazard_areas_df


def _extract_layer(module_logger, fema_extractor, layer):
    module_logger.info("Extracting %s...", layer["name"])
    service_layer = extract.ServiceLayer(
        f'{fema_extractor.url}/{layer["number"]}', timeout=config.TIMEOUT, where_clause="DFIRM_ID LIKE '49%'"
    )
    layer_df = fema_extractor.get_features(service_layer)
    return layer_df


def _transform_layer(module_logger, layer, layer_df):
    module_logger.info("Transforming %s...", layer["name"])
    if layer["name"] == "S_Fld_Haz_Ar":
        layer_df = _hazard_areas(layer_df)

    #: make columns match
    layer_df.columns = [col.lower() if col not in ["SHAPE", "OBJECTID"] else col for col in layer_df.columns]
    layer_df.rename(columns={"globalid": "global_id"}, inplace=True)
    layer_df.drop(columns=["shape.stlength()", "shape.starea()"], errors="ignore", inplace=True)

    #: Fix various field types if the layer has them set
    for method, list_name in zip(
        [
            transform.DataCleaning.switch_to_datetime,
            transform.DataCleaning.switch_to_float,
            transform.DataCleaning.switch_to_nullable_int,
        ],
        ["date_fields", "double_fields", "int_fields"],
    ):
        try:
            layer_df = method(layer_df, layer[list_name])
        except KeyError:
            pass

    #: Drop rows with empty geometries
    empty_geometries = layer_df["SHAPE"].isnull()
    if empty_geometries.any():
        module_logger.warning(
            "Dropping %s rows with empty geometries (indices %s)",
            empty_geometries.sum(),
            empty_geometries[empty_geometries].index.tolist(),
        )
        layer_df.dropna(subset=["SHAPE"], inplace=True)

    return layer_df


def _load_layer(module_logger, tempdir, gis, layer, layer_df):
    run_dir = Path(tempdir) / layer["name"]
    try:
        run_dir.mkdir()
    except FileExistsError:
        shutil.rmtree(run_dir)
        run_dir.mkdir()

    module_logger.info("Loading %s...", layer["name"])
    feature_layer = load.ServiceUpdater(gis, layer["itemid"], working_dir=run_dir)
    features_loaded = feature_layer.truncate_and_load(layer_df, save_old=False)
    return features_loaded


def _update_hazard_layer_symbology(gis):
    layer_item = gis.content.get(config.FEMA_LAYERS["S_Fld_Haz_Ar"]["itemid"])
    layer_data = layer_item.get_data()

    #: Try to get the symbology file from a specific location in the container (as per dockerfile's COPY)
    try:
        json_path = Path("/app/src/nfhl/fld_haz_ar_drawingInfo.json")
        with json_path.open("r", encoding="utf-8") as symbology_file:
            symbology_json = json.load(symbology_file)

    #: otherwise, use a relative path
    except FileNotFoundError:
        json_path = Path(__file__).parent / "fld_haz_ar_drawingInfo.json"
        with json_path.open("r", encoding="utf-8") as symbology_file:
            symbology_json = json.load(symbology_file)

    layer_data["layers"][0]["layerDefinition"]["drawingInfo"] = symbology_json
    result = utils.retry(layer_item.update, item_properties={"text": json.dumps(layer_data)})
    return result


def _delete_existing_gdb_item(gis, gdb_item_name, module_logger):
    module_logger.info("Searching for and deleting GDB item '%s' if needed...", gdb_item_name)

    searches = gis.content.search(query=gdb_item_name, item_type="File Geodatabase")
    if not searches:
        module_logger.info("GDB item '%s' not found, proceeding", gdb_item_name)
        return
    if len(searches) > 1:
        raise ValueError(f"Multiple GDBs found matching {gdb_item_name}")
    gdb_item = searches[0]
    try:
        gdb_item.delete()
    except Exception as error:
        raise ValueError(f"Cannot delete '{gdb_item_name}' ({gdb_item.itemid})") from error


def process():  # pylint: disable=too-many-locals
    """The main function that does all the work."""

    #: Set up secrets, tempdir, supervisor, and logging
    start = datetime.now()

    secrets = SimpleNamespace(**_get_secrets())

    with TemporaryDirectory() as tempdir:
        tempdir_path = Path(tempdir)
        log_name = f'{config.LOG_FILE_NAME}_{start.strftime("%Y%m%d-%H%M%S")}.txt'
        log_path = tempdir_path / log_name

        skid_supervisor = _initialize(log_path, secrets.SENDGRID_API_KEY)
        #: Get our GIS object via the ArcGIS API for Python
        gis = arcgis.gis.GIS(config.AGOL_ORG, secrets.AGOL_USER, secrets.AGOL_PASSWORD)
        fema_extractor = extract.RESTServiceLoader(config.SERVICE_URL, timeout=config.TIMEOUT)
        module_logger = logging.getLogger(config.SKID_NAME)

        feature_counts = {}

        for name, layer in config.FEMA_LAYERS.items():
            try:
                layer_df = utils.retry(_extract_layer, module_logger, fema_extractor, layer)
                layer_df = utils.retry(_transform_layer, module_logger, layer, layer_df)
                _delete_existing_gdb_item(gis, "palletjack Temporary gdb upload", module_logger)
                features_loaded = utils.retry(_load_layer, module_logger, tempdir, gis, layer, layer_df)
                del layer_df
            except Exception:
                module_logger.exception("Error loading %s", name)
                features_loaded = "error"
            feature_counts[name] = features_loaded

        module_logger.info("Updating hazard area symbology...")
        try:
            hazard_area_result = _update_hazard_layer_symbology(gis)
        except Exception:
            module_logger.exception("Error updating hazard area symbology")
            hazard_area_result = False

        end = datetime.now()

        summary_message = MessageDetails()
        summary_message.subject = f"{config.SKID_NAME} Update Summary"
        summary_rows = [
            f'{config.SKID_NAME} update {start.strftime("%Y-%m-%d")}',
            "=" * 20,
            "",
            f'Start time: {start.strftime("%H:%M:%S")}',
            f'End time: {end.strftime("%H:%M:%S")}',
            f"Duration: {str(end-start)}",
            "Update Counts:",
        ]
        summary_rows.extend([f"{name}: {count}" for name, count in feature_counts.items()])
        summary_rows.append(f"Hazard Area Symbology Updated: {hazard_area_result}")

        summary_message.message = "\n".join(summary_rows)
        summary_message.attachments = tempdir_path / log_name

        skid_supervisor.notify(summary_message)

        #: Remove file handler so the tempdir will close properly
        loggers = [logging.getLogger(config.SKID_NAME), logging.getLogger("palletjack")]
        _remove_log_file_handlers(log_name, loggers)


if __name__ == "__main__":
    process()
