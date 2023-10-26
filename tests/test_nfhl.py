from nfhl import main


def test_get_secrets_from_gcp_location(mocker):
    mocker.patch('pathlib.Path.exists', return_value=True)
    mocker.patch('pathlib.Path.read_text', return_value='{"foo":"bar"}')

    secrets = main._get_secrets()

    assert secrets == {'foo': 'bar'}


def test_get_secrets_from_local_location(mocker):
    exists_mock = mocker.Mock(side_effect=[False, True])
    mocker.patch('pathlib.Path.exists', new=exists_mock)
    mocker.patch('pathlib.Path.read_text', return_value='{"foo":"bar"}')

    secrets = main._get_secrets()

    assert secrets == {'foo': 'bar'}
    assert exists_mock.call_count == 2


def test_process_continues_on_one_layer_failure(mocker, caplog):
    mocker.patch.multiple(
        'nfhl.main',
        _get_secrets=mocker.DEFAULT,
        _initialize=mocker.DEFAULT,
        _update_hazard_layer_symbology=mocker.DEFAULT,
        SimpleNamespace=mocker.DEFAULT,
    )
    mocker.patch('nfhl.main.arcgis')
    mocker.patch('nfhl.main.extract')
    mocker.patch('nfhl.main.config', FEMA_LAYERS={'one': {'name': 'one'}, 'two': {'name': 'two'}}, SKID_NAME='foo')
    mocker.patch('palletjack.utils.sleep')

    operate_mock = mocker.patch('nfhl.main._operate_on_layer')
    operate_mock.side_effect = [Exception('one_1'), Exception('one_2'), Exception('one_3'), Exception('one_4'), 42]

    main.process()

    assert 'Error loading one' in caplog.text
    assert operate_mock.call_count == 5
    assert operate_mock.call_args.args[4] == {'name': 'two'}


def test_process_continues_on_failed_area_hazard_symbology_update(mocker, caplog):
    mocker.patch.multiple(
        'nfhl.main',
        _get_secrets=mocker.DEFAULT,
        _initialize=mocker.DEFAULT,
        _operate_on_layer=mocker.DEFAULT,
        SimpleNamespace=mocker.DEFAULT,
    )
    mocker.patch('nfhl.main.arcgis')
    mocker.patch('nfhl.main.extract')
    mocker.patch('nfhl.main.config', FEMA_LAYERS={'one': {'name': 'one'}, 'two': {'name': 'two'}}, SKID_NAME='foo')
    # mocker.patch('palletjack.utils.sleep')

    update_mock = mocker.patch('nfhl.main._update_hazard_layer_symbology')
    update_mock.side_effect = [Exception('symbology update failed')]

    main.process()

    assert 'symbology update failed' in caplog.text
    assert 'Error updating hazard area symbology' in caplog.text
