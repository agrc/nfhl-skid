# nfhl-skid

![Build Status](https://github.com/agrc/nfhl-skid/workflows/Build%20and%20Test/badge.svg)

A script for updating flood map layers with the latest info from FEMA's NFHL layers at <https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer>.

## Script Overview

nfhl-skid uses [palletjack](https://github.com/agrc/palletjack) to extract features from the FEMA MapServices one layer at a time using a SQL query to filter results to `DFIRM_ID LIKE '49%'` (49 being Utah's FIPS code). Each extracted layer is then used to overwrite a specified AGOL hosted feature service. These feature services are used by DEM in their flood map portal.

The script uses robust retry logic to give it the best chance of succeeding even with FEMA's less-than-reliable (and/or overtaxed) server. In addition to the retry logic built into the individual components of palletjack, nfhl-skid will individually retry the extract, transform, and load steps of each layer three times (for a total of four attempts) to ensure that temporarily slow responses from the server don't scuttle the whole layer.

In addition, if one layer fails it notes this and moves on to the next, ensuring that the failure of one layer will not cause the entire skid to fail. However, because it uses truncate and load instead of in-line updating, failures in the load to AGOL step may leave empty feature classes. Existing data are saved to a `tempfile.TemporaryDirectory` during the truncate and load, but this directory is cleaned up when the script exits.

## Runtime Environment

nfhl-skid is designed to run in Google Cloud Run but can also be run locally for development, testing, and one-off updates. The `push.yml` workflow builds and tests the python package, builds the container for Cloud Run, deploys the container, and sets up a Cloud Scheduler job to run it at a regular interval.

You must have already created a GCP project for the skid to run in, preferably via terraform. This should include service accounts for github actions to deploy the container, Cloud Run to actually run the container, and Cloud Scheduler to kick off the run. It should also include Artifact Registry to store the container builds, Secrets Manager to handle sensitive info, and Log Monitoring for alerts.

## Handling Secrets and Configuration Files

nfhl-skid uses GCP Secrets Manager to make secrets available to the function. They are mounted as a local file specified in the GitHub CI action workflow. For local development, the `secrets.json` file holds all the login info, etc. A template is available in the repo's root directory. It attempts to read the mounted secrets file first, and failing this will try to read a local secrets.json.

A separate `config.py` module holds non-secret configuration values. These are accessed by importing the module and accessing them directly. This is where you specify the layers to download and the AGOL item IDs to update. Because these values are not senstitive, they are stored in the repo itself and get installed in the container via the build process.

## Attribution

This project was developed with the assistance of [GitHub Copilot](https://github.com/features/copilot).
