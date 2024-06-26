# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# pylint: disable=unused-argument, import-outside-toplevel, line-too-long

import json
from datetime import datetime
from io import BytesIO
from typing import Any
from unittest.mock import Mock
from uuid import UUID

import pytest
from flask import current_app
from freezegun import freeze_time
from pytest_mock import MockFixture
from sqlalchemy.orm.session import Session

from superset import db
from superset.db_engine_specs.sqlite import SqliteEngineSpec


def test_filter_by_uuid(
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test that we can filter databases by UUID.

    Note: this functionality is not used by the Superset UI, but is needed by 3rd
    party tools that use the Superset API. If this tests breaks, please make sure
    that the functionality is properly deprecated between major versions with
    enough warning so that tools can be adapted.
    """
    from superset.databases.api import DatabaseRestApi
    from superset.models.core import Database

    DatabaseRestApi.datamodel.session = session

    # create table for databases
    Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member
    db.session.add(
        Database(
            database_name="my_db",
            sqlalchemy_uri="sqlite://",
            uuid=UUID("7c1b7880-a59d-47cd-8bf1-f1eb8d2863cb"),
        )
    )
    db.session.commit()

    response = client.get(
        "/api/v1/database/?q=(filters:!((col:uuid,opr:eq,value:"
        "%277c1b7880-a59d-47cd-8bf1-f1eb8d2863cb%27)))"
    )
    assert response.status_code == 200

    payload = response.json
    assert len(payload["result"]) == 1
    assert payload["result"][0]["uuid"] == "7c1b7880-a59d-47cd-8bf1-f1eb8d2863cb"


def test_post_with_uuid(
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test that we can set the database UUID when creating it.
    """
    from superset.models.core import Database

    # create table for databases
    Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member

    response = client.post(
        "/api/v1/database/",
        json={
            "database_name": "my_db",
            "sqlalchemy_uri": "sqlite://",
            "uuid": "7c1b7880-a59d-47cd-8bf1-f1eb8d2863cb",
        },
    )
    assert response.status_code == 201

    # check that response includes UUID
    payload = response.json
    assert payload["result"]["uuid"] == "7c1b7880-a59d-47cd-8bf1-f1eb8d2863cb"

    database = db.session.query(Database).one()
    assert database.uuid == UUID("7c1b7880-a59d-47cd-8bf1-f1eb8d2863cb")


def test_password_mask(
    mocker: MockFixture,
    app: Any,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test that sensitive information is masked.
    """
    from superset.databases.api import DatabaseRestApi
    from superset.models.core import Database

    DatabaseRestApi.datamodel.session = session

    # create table for databases
    Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member

    database = Database(
        uuid=UUID("02feae18-2dd6-4bb4-a9c0-49e9d4f29d58"),
        database_name="my_database",
        sqlalchemy_uri="gsheets://",
        encrypted_extra=json.dumps(
            {
                "service_account_info": {
                    "type": "service_account",
                    "project_id": "black-sanctum-314419",
                    "private_key_id": "259b0d419a8f840056158763ff54d8b08f7b8173",
                    "private_key": "SECRET",
                    "client_email": "google-spreadsheets-demo-servi@black-sanctum-314419.iam.gserviceaccount.com",
                    "client_id": "114567578578109757129",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/google-spreadsheets-demo-servi%40black-sanctum-314419.iam.gserviceaccount.com",
                },
            }
        ),
    )
    db.session.add(database)
    db.session.commit()

    # mock the lookup so that we don't need to include the driver
    mocker.patch("sqlalchemy.engine.URL.get_driver_name", return_value="gsheets")
    mocker.patch("superset.utils.log.DBEventLogger.log")

    response = client.get("/api/v1/database/1/connection")

    # check that private key is masked
    assert (
        response.json["result"]["parameters"]["service_account_info"]["private_key"]
        == "XXXXXXXXXX"
    )
    assert "encrypted_extra" not in response.json["result"]


def test_database_connection(
    mocker: MockFixture,
    app: Any,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test that connection info is only returned in ``api/v1/database/${id}/connection``.
    """
    from superset.databases.api import DatabaseRestApi
    from superset.models.core import Database

    DatabaseRestApi.datamodel.session = session

    # create table for databases
    Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member

    database = Database(
        uuid=UUID("02feae18-2dd6-4bb4-a9c0-49e9d4f29d58"),
        database_name="my_database",
        sqlalchemy_uri="gsheets://",
        encrypted_extra=json.dumps(
            {
                "service_account_info": {
                    "type": "service_account",
                    "project_id": "black-sanctum-314419",
                    "private_key_id": "259b0d419a8f840056158763ff54d8b08f7b8173",
                    "private_key": "SECRET",
                    "client_email": "google-spreadsheets-demo-servi@black-sanctum-314419.iam.gserviceaccount.com",
                    "client_id": "114567578578109757129",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/google-spreadsheets-demo-servi%40black-sanctum-314419.iam.gserviceaccount.com",
                },
            }
        ),
    )
    db.session.add(database)
    db.session.commit()

    # mock the lookup so that we don't need to include the driver
    mocker.patch("sqlalchemy.engine.URL.get_driver_name", return_value="gsheets")
    mocker.patch("superset.utils.log.DBEventLogger.log")

    response = client.get("/api/v1/database/1/connection")
    assert response.json == {
        "id": 1,
        "result": {
            "allow_ctas": False,
            "allow_cvas": False,
            "allow_dml": False,
            "allow_file_upload": False,
            "allow_run_async": False,
            "backend": "gsheets",
            "cache_timeout": None,
            "configuration_method": "sqlalchemy_form",
            "database_name": "my_database",
            "driver": "gsheets",
            "engine_information": {
                "disable_ssh_tunneling": True,
                "supports_file_upload": True,
            },
            "expose_in_sqllab": True,
            "extra": '{\n    "metadata_params": {},\n    "engine_params": {},\n    "metadata_cache_timeout": {},\n    "schemas_allowed_for_file_upload": []\n}\n',
            "force_ctas_schema": None,
            "id": 1,
            "impersonate_user": False,
            "is_managed_externally": False,
            "masked_encrypted_extra": json.dumps(
                {
                    "service_account_info": {
                        "type": "service_account",
                        "project_id": "black-sanctum-314419",
                        "private_key_id": "259b0d419a8f840056158763ff54d8b08f7b8173",
                        "private_key": "XXXXXXXXXX",
                        "client_email": "google-spreadsheets-demo-servi@black-sanctum-314419.iam.gserviceaccount.com",
                        "client_id": "114567578578109757129",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/google-spreadsheets-demo-servi%40black-sanctum-314419.iam.gserviceaccount.com",
                    }
                }
            ),
            "parameters": {
                "service_account_info": {
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "client_email": "google-spreadsheets-demo-servi@black-sanctum-314419.iam.gserviceaccount.com",
                    "client_id": "114567578578109757129",
                    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/google-spreadsheets-demo-servi%40black-sanctum-314419.iam.gserviceaccount.com",
                    "private_key": "XXXXXXXXXX",
                    "private_key_id": "259b0d419a8f840056158763ff54d8b08f7b8173",
                    "project_id": "black-sanctum-314419",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "type": "service_account",
                }
            },
            "parameters_schema": {
                "properties": {
                    "catalog": {"type": "object"},
                    "service_account_info": {
                        "description": "Contents of GSheets JSON credentials.",
                        "type": "string",
                        "x-encrypted-extra": True,
                    },
                },
                "type": "object",
            },
            "server_cert": None,
            "sqlalchemy_uri": "gsheets://",
            "uuid": "02feae18-2dd6-4bb4-a9c0-49e9d4f29d58",
        },
    }

    response = client.get("/api/v1/database/1")
    assert response.json == {
        "id": 1,
        "result": {
            "allow_ctas": False,
            "allow_cvas": False,
            "allow_dml": False,
            "allow_file_upload": False,
            "allow_run_async": False,
            "backend": "gsheets",
            "cache_timeout": None,
            "configuration_method": "sqlalchemy_form",
            "database_name": "my_database",
            "driver": "gsheets",
            "engine_information": {
                "disable_ssh_tunneling": True,
                "supports_file_upload": True,
            },
            "expose_in_sqllab": True,
            "force_ctas_schema": None,
            "id": 1,
            "impersonate_user": False,
            "is_managed_externally": False,
            "uuid": "02feae18-2dd6-4bb4-a9c0-49e9d4f29d58",
        },
    }


@pytest.mark.skip(reason="Works locally but fails on CI")
def test_update_with_password_mask(
    app: Any,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test that an update with a masked password doesn't overwrite the existing password.
    """
    from superset.databases.api import DatabaseRestApi
    from superset.models.core import Database

    DatabaseRestApi.datamodel.session = session

    # create table for databases
    Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member

    database = Database(
        database_name="my_database",
        sqlalchemy_uri="gsheets://",
        encrypted_extra=json.dumps(
            {
                "service_account_info": {
                    "project_id": "black-sanctum-314419",
                    "private_key": "SECRET",
                },
            }
        ),
    )
    db.session.add(database)
    db.session.commit()

    client.put(
        "/api/v1/database/1",
        json={
            "encrypted_extra": json.dumps(
                {
                    "service_account_info": {
                        "project_id": "yellow-unicorn-314419",
                        "private_key": "XXXXXXXXXX",
                    },
                }
            ),
        },
    )
    database = db.session.query(Database).one()
    assert (
        database.encrypted_extra
        == '{"service_account_info": {"project_id": "yellow-unicorn-314419", "private_key": "SECRET"}}'
    )


def test_non_zip_import(client: Any, full_api_access: None) -> None:
    """
    Test that non-ZIP imports are not allowed.
    """
    buf = BytesIO(b"definitely_not_a_zip_file")
    form_data = {
        "formData": (buf, "evil.pdf"),
    }
    response = client.post(
        "/api/v1/database/import/",
        data=form_data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert response.json == {
        "errors": [
            {
                "message": "Not a ZIP file",
                "error_type": "GENERIC_COMMAND_ERROR",
                "level": "warning",
                "extra": {
                    "issue_codes": [
                        {
                            "code": 1010,
                            "message": "Issue 1010 - Superset encountered an error while running a command.",
                        }
                    ]
                },
            }
        ]
    }


def test_delete_ssh_tunnel(
    mocker: MockFixture,
    app: Any,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test that we can delete SSH Tunnel
    """
    with app.app_context():
        from superset.daos.database import DatabaseDAO
        from superset.databases.api import DatabaseRestApi
        from superset.databases.ssh_tunnel.models import SSHTunnel
        from superset.models.core import Database

        DatabaseRestApi.datamodel.session = session

        # create table for databases
        Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member

        # Create our Database
        database = Database(
            database_name="my_database",
            sqlalchemy_uri="gsheets://",
            encrypted_extra=json.dumps(
                {
                    "service_account_info": {
                        "type": "service_account",
                        "project_id": "black-sanctum-314419",
                        "private_key_id": "259b0d419a8f840056158763ff54d8b08f7b8173",
                        "private_key": "SECRET",
                        "client_email": "google-spreadsheets-demo-servi@black-sanctum-314419.iam.gserviceaccount.com",
                        "client_id": "SSH_TUNNEL_CREDENTIALS_CLIENT",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/google-spreadsheets-demo-servi%40black-sanctum-314419.iam.gserviceaccount.com",
                    },
                }
            ),
        )
        db.session.add(database)
        db.session.commit()

        # mock the lookup so that we don't need to include the driver
        mocker.patch("sqlalchemy.engine.URL.get_driver_name", return_value="gsheets")
        mocker.patch("superset.utils.log.DBEventLogger.log")
        mocker.patch(
            "superset.commands.database.ssh_tunnel.delete.is_feature_enabled",
            return_value=True,
        )

        # Create our SSHTunnel
        tunnel = SSHTunnel(
            database_id=1,
            database=database,
        )

        db.session.add(tunnel)
        db.session.commit()

        # Get our recently created SSHTunnel
        response_tunnel = DatabaseDAO.get_ssh_tunnel(1)
        assert response_tunnel
        assert isinstance(response_tunnel, SSHTunnel)
        assert 1 == response_tunnel.database_id

        # Delete the recently created SSHTunnel
        response_delete_tunnel = client.delete(
            f"/api/v1/database/{database.id}/ssh_tunnel/"
        )
        assert response_delete_tunnel.json["message"] == "OK"

        response_tunnel = DatabaseDAO.get_ssh_tunnel(1)
        assert response_tunnel is None


def test_delete_ssh_tunnel_not_found(
    mocker: MockFixture,
    app: Any,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test that we cannot delete a tunnel that does not exist
    """
    with app.app_context():
        from superset.daos.database import DatabaseDAO
        from superset.databases.api import DatabaseRestApi
        from superset.databases.ssh_tunnel.models import SSHTunnel
        from superset.models.core import Database

        DatabaseRestApi.datamodel.session = session

        # create table for databases
        Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member

        # Create our Database
        database = Database(
            database_name="my_database",
            sqlalchemy_uri="gsheets://",
            encrypted_extra=json.dumps(
                {
                    "service_account_info": {
                        "type": "service_account",
                        "project_id": "black-sanctum-314419",
                        "private_key_id": "259b0d419a8f840056158763ff54d8b08f7b8173",
                        "private_key": "SECRET",
                        "client_email": "google-spreadsheets-demo-servi@black-sanctum-314419.iam.gserviceaccount.com",
                        "client_id": "SSH_TUNNEL_CREDENTIALS_CLIENT",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/google-spreadsheets-demo-servi%40black-sanctum-314419.iam.gserviceaccount.com",
                    },
                }
            ),
        )
        db.session.add(database)
        db.session.commit()

        # mock the lookup so that we don't need to include the driver
        mocker.patch("sqlalchemy.engine.URL.get_driver_name", return_value="gsheets")
        mocker.patch("superset.utils.log.DBEventLogger.log")
        mocker.patch(
            "superset.commands.database.ssh_tunnel.delete.is_feature_enabled",
            return_value=True,
        )

        # Create our SSHTunnel
        tunnel = SSHTunnel(
            database_id=1,
            database=database,
        )

        db.session.add(tunnel)
        db.session.commit()

        # Delete the recently created SSHTunnel
        response_delete_tunnel = client.delete("/api/v1/database/2/ssh_tunnel/")
        assert response_delete_tunnel.json["message"] == "Not found"

        # Get our recently created SSHTunnel
        response_tunnel = DatabaseDAO.get_ssh_tunnel(1)
        assert response_tunnel
        assert isinstance(response_tunnel, SSHTunnel)
        assert 1 == response_tunnel.database_id

        response_tunnel = DatabaseDAO.get_ssh_tunnel(2)
        assert response_tunnel is None


def test_apply_dynamic_database_filter(
    mocker: MockFixture,
    app: Any,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test that we can filter the list of databases.
    First test the default behavior without a filter and then
    defining a filter function and patching the config to get
    the filtered results.
    """
    with app.app_context():
        from superset.daos.database import DatabaseDAO
        from superset.databases.api import DatabaseRestApi
        from superset.databases.ssh_tunnel.models import SSHTunnel
        from superset.models.core import Database

        DatabaseRestApi.datamodel.session = session

        # create table for databases
        Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member

        # Create our First Database
        database = Database(
            database_name="first-database",
            sqlalchemy_uri="gsheets://",
            encrypted_extra=json.dumps(
                {
                    "metadata_params": {},
                    "engine_params": {},
                    "metadata_cache_timeout": {},
                    "schemas_allowed_for_file_upload": [],
                }
            ),
        )
        db.session.add(database)
        db.session.commit()

        # Create our Second Database
        database = Database(
            database_name="second-database",
            sqlalchemy_uri="gsheets://",
            encrypted_extra=json.dumps(
                {
                    "metadata_params": {},
                    "engine_params": {},
                    "metadata_cache_timeout": {},
                    "schemas_allowed_for_file_upload": [],
                }
            ),
        )
        db.session.add(database)
        db.session.commit()

        # mock the lookup so that we don't need to include the driver
        mocker.patch("sqlalchemy.engine.URL.get_driver_name", return_value="gsheets")
        mocker.patch("superset.utils.log.DBEventLogger.log")
        mocker.patch(
            "superset.commands.database.ssh_tunnel.delete.is_feature_enabled",
            return_value=False,
        )

        def _base_filter(query):
            from superset.models.core import Database

            return query.filter(Database.database_name.startswith("second"))

        # Create a mock object
        base_filter_mock = Mock(side_effect=_base_filter)

        # Get our recently created Databases
        response_databases = DatabaseDAO.find_all()
        assert response_databases
        expected_db_names = ["first-database", "second-database"]
        actual_db_names = [db.database_name for db in response_databases]
        assert actual_db_names == expected_db_names

        # Ensure that the filter has not been called because it's not in our config
        assert base_filter_mock.call_count == 0

        original_config = current_app.config.copy()
        original_config["EXTRA_DYNAMIC_QUERY_FILTERS"] = {"databases": base_filter_mock}

        mocker.patch("superset.views.filters.current_app.config", new=original_config)
        # Get filtered list
        response_databases = DatabaseDAO.find_all()
        assert response_databases
        expected_db_names = ["second-database"]
        actual_db_names = [db.database_name for db in response_databases]
        assert actual_db_names == expected_db_names

        # Ensure that the filter has been called once
        assert base_filter_mock.call_count == 1


def test_oauth2_happy_path(
    mocker: MockFixture,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test the OAuth2 endpoint when everything goes well.
    """
    from superset.databases.api import DatabaseRestApi
    from superset.models.core import Database, DatabaseUserOAuth2Tokens

    DatabaseRestApi.datamodel.session = session

    # create table for databases
    Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member
    db.session.add(
        Database(
            database_name="my_db",
            sqlalchemy_uri="sqlite://",
            uuid=UUID("7c1b7880-a59d-47cd-8bf1-f1eb8d2863cb"),
        )
    )
    db.session.commit()

    mocker.patch.object(
        SqliteEngineSpec,
        "get_oauth2_config",
        return_value={"id": "one", "secret": "two"},
    )
    get_oauth2_token = mocker.patch.object(SqliteEngineSpec, "get_oauth2_token")
    get_oauth2_token.return_value = {
        "access_token": "YYY",
        "expires_in": 3600,
        "refresh_token": "ZZZ",
    }

    state = {
        "user_id": 1,
        "database_id": 1,
        "tab_id": 42,
    }
    decode_oauth2_state = mocker.patch("superset.databases.api.decode_oauth2_state")
    decode_oauth2_state.return_value = state

    mocker.patch("superset.databases.api.render_template", return_value="OK")

    with freeze_time("2024-01-01T00:00:00Z"):
        response = client.get(
            "/api/v1/database/oauth2/",
            query_string={
                "state": "some%2Estate",
                "code": "XXX",
            },
        )

    assert response.status_code == 200
    decode_oauth2_state.assert_called_with("some%2Estate")
    get_oauth2_token.assert_called_with({"id": "one", "secret": "two"}, "XXX")

    token = db.session.query(DatabaseUserOAuth2Tokens).one()
    assert token.user_id == 1
    assert token.database_id == 1
    assert token.access_token == "YYY"
    assert token.access_token_expiration == datetime(2024, 1, 1, 1, 0)
    assert token.refresh_token == "ZZZ"


def test_oauth2_multiple_tokens(
    mocker: MockFixture,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test the OAuth2 endpoint when a second token is added.
    """
    from superset.databases.api import DatabaseRestApi
    from superset.models.core import Database, DatabaseUserOAuth2Tokens

    DatabaseRestApi.datamodel.session = session

    # create table for databases
    Database.metadata.create_all(session.get_bind())  # pylint: disable=no-member
    db.session.add(
        Database(
            database_name="my_db",
            sqlalchemy_uri="sqlite://",
            uuid=UUID("7c1b7880-a59d-47cd-8bf1-f1eb8d2863cb"),
        )
    )
    db.session.commit()

    mocker.patch.object(
        SqliteEngineSpec,
        "get_oauth2_config",
        return_value={"id": "one", "secret": "two"},
    )
    get_oauth2_token = mocker.patch.object(SqliteEngineSpec, "get_oauth2_token")
    get_oauth2_token.side_effect = [
        {
            "access_token": "YYY",
            "expires_in": 3600,
            "refresh_token": "ZZZ",
        },
        {
            "access_token": "YYY2",
            "expires_in": 3600,
            "refresh_token": "ZZZ2",
        },
    ]

    state = {
        "user_id": 1,
        "database_id": 1,
        "tab_id": 42,
    }
    decode_oauth2_state = mocker.patch("superset.databases.api.decode_oauth2_state")
    decode_oauth2_state.return_value = state

    mocker.patch("superset.databases.api.render_template", return_value="OK")

    with freeze_time("2024-01-01T00:00:00Z"):
        response = client.get(
            "/api/v1/database/oauth2/",
            query_string={
                "state": "some%2Estate",
                "code": "XXX",
            },
        )

        # second request should delete token from the first request
        response = client.get(
            "/api/v1/database/oauth2/",
            query_string={
                "state": "some%2Estate",
                "code": "XXX",
            },
        )

    assert response.status_code == 200
    tokens = db.session.query(DatabaseUserOAuth2Tokens).all()
    assert len(tokens) == 1
    token = tokens[0]
    assert token.access_token == "YYY2"
    assert token.refresh_token == "ZZZ2"


def test_oauth2_error(
    mocker: MockFixture,
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test the OAuth2 endpoint when OAuth2 errors.
    """
    response = client.get(
        "/api/v1/database/oauth2/",
        query_string={
            "error": "Something bad hapened",
        },
    )

    assert response.status_code == 500
    assert response.json == {
        "errors": [
            {
                "message": "Something went wrong while doing OAuth2",
                "error_type": "OAUTH2_REDIRECT_ERROR",
                "level": "error",
                "extra": {"error": "Something bad hapened"},
            }
        ]
    }
