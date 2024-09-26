import json
import unittest
import uuid

import mock

from mock import patch

from system_baseline import app
from system_baseline.models import SystemBaselineMappedSystem

from . import fixtures


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.rbac_patcher = patch("system_baseline.views.v1.view_helpers.ensure_has_permission")
        patched_rbac = self.rbac_patcher.start()
        patched_rbac.return_value = None  # validate all RBAC requests
        self.addCleanup(self.stopPatches)
        test_connexion_app = app.create_app()
        self.client = test_connexion_app.test_client

    def stopPatches(self):
        self.rbac_patcher.stop()


class ApiSystemsAssociationTests(ApiTest):
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def setUp(self, mock_fetch_systems):
        super(ApiSystemsAssociationTests, self).setUp()

        with self.client() as client:
            self.system_ids = [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            ]

            mock_fetch_systems.return_value = [
                fixtures.a_system_with_profile(system_id) for system_id in self.system_ids
            ]

            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_ONE_LOAD,
            )

            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.baseline_id = [b["id"] for b in result["data"]][0]

            response = client.post(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
                json={"system_ids": self.system_ids},
            )
            self.assertEqual(response.status_code, 200)

    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def tearDown(self, mock_fetch_systems):
        super(ApiSystemsAssociationTests, self).tearDown()
        with self.client() as client:
            mock_fetch_systems.return_value = [
                fixtures.a_system_with_profile(system_id) for system_id in self.system_ids
            ]
            # get all baselines
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            baselines = json.loads(response.content)["data"]

            for baseline in baselines:
                # get systems for baseline
                response = client.get(
                    "api/system-baseline/v1/baselines/" + baseline["id"] + "/systems",
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

                system_ids = json.loads(response.content)["system_ids"]

                # delete systems
                response = client.post(
                    "api/system-baseline/v1/baselines/"
                    + baseline["id"]
                    + "/systems/deletion_request",
                    headers=fixtures.AUTH_HEADER,
                    json={"system_ids": system_ids},
                )
                self.assertEqual(response.status_code, 200)

                # delete baseline
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    def test_list_systems_with_baseline(self):
        with self.client() as client:
            response = client.get(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]
            self.assertEqual(len(response_system_ids), 3)

            for system_id in self.system_ids:
                self.assertIn(system_id, response_system_ids)

    @unittest.skip("drift is being shut down")
    def test_delete_systems_with_baseline(self):
        with self.client() as client:
            # to delete
            system_ids = [
                self.system_ids[0],
                self.system_ids[1],
            ]

            # delete systems
            response = client.post(
                "api/system-baseline/v1/baselines/"
                + self.baseline_id
                + "/systems/deletion_request",
                headers=fixtures.AUTH_HEADER,
                json={"system_ids": system_ids},
            )
            self.assertEqual(response.status_code, 200)

            # read what systems persisted
            response = client.get(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)
            self.assertEqual(len(response_system_ids), 1)

    @unittest.skip("drift is being shut down")
    def test_delete_nonexistent_system(self):
        with self.client() as client:
            # to delete
            system_ids = [
                str(uuid.uuid4()),
            ]

            # delete systems
            response = client.post(
                "api/system-baseline/v1/baselines/"
                + self.baseline_id
                + "/systems/deletion_request",
                headers=fixtures.AUTH_HEADER,
                json=system_ids,
            )
            self.assertEqual(response.status_code, 400)

            # read what systems persisted
            response = client.get(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]
            self.assertNotIn(system_ids[0], response_system_ids)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_adding_few_systems(self, mock_fetch_systems):
        with self.client() as client:
            # to create
            system_ids = [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            ]

            mock_fetch_systems.return_value = [
                fixtures.a_system_with_profile(system_id) for system_id in system_ids
            ]

            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            baseline_id = [b["id"] for b in result["data"]][0]

            response = client.post(
                "api/system-baseline/v1/baselines/" + baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
                json={"system_ids": system_ids},
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]
            self.assertEqual(set(system_ids), set(response_system_ids).intersection(system_ids))

            for system_id in system_ids:
                self.assertIn(system_id, response_system_ids)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_deleting_systems_by_id(
        self,
        mock_fetch_systems,
    ):
        with self.client() as client:
            # to create
            system_ids = [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            ]

            mock_fetch_systems.return_value = [
                fixtures.a_system_with_profile(system_id) for system_id in system_ids
            ]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            baseline_id = [b["id"] for b in result["data"]][0]

            response = client.post(
                "api/system-baseline/v1/baselines/" + baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
                json={"system_ids": system_ids},
            )
            self.assertEqual(response.status_code, 200)

            system_ids_to_delete = system_ids[0:2]
            system_ids_to_remain = system_ids[2:]

            response = client.delete(
                "api/system-baseline/internal/v1/systems/%s" % ",".join(system_ids_to_delete),
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            # read what systems persisted
            response = client.get(
                "api/system-baseline/v1/baselines/" + baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]

            # deleted systems
            for system_id in system_ids_to_delete:
                self.assertNotIn(system_id, response_system_ids)

            # remaining systems
            for system_id in system_ids_to_remain:
                self.assertIn(system_id, response_system_ids)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_creating_deletion_request_for_systems_by_id(self, mock_fetch_systems):
        with self.client() as client:
            # to create
            system_ids = [
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            ]

            mock_fetch_systems.return_value = [
                fixtures.a_system_with_profile(system_id) for system_id in system_ids
            ]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            baseline_id = [b["id"] for b in result["data"]][0]

            response = client.post(
                "api/system-baseline/v1/baselines/" + baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
                json={"system_ids": system_ids},
            )
            self.assertEqual(response.status_code, 200)

            system_ids_to_delete = system_ids[0:2]
            system_ids_to_remain = system_ids[2:]

            response = client.post(
                "api/system-baseline/internal/v1/systems/deletion_request",
                headers=fixtures.AUTH_HEADER,
                json={"system_ids": system_ids_to_delete},
            )
            self.assertEqual(response.status_code, 200)

            # read what systems persisted
            response = client.get(
                "api/system-baseline/v1/baselines/" + baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]

            # deleted systems
            for system_id in system_ids_to_delete:
                self.assertNotIn(system_id, response_system_ids)

            # remaining systems
            for system_id in system_ids_to_remain:
                self.assertIn(system_id, response_system_ids)


class InternalApiBaselinesTests(ApiTest):
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def setUp(self, mock_fetch_systems):
        super(InternalApiBaselinesTests, self).setUp()
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            for baseline_load in [
                fixtures.BASELINE_ONE_LOAD,
                fixtures.BASELINE_TWO_LOAD,
                fixtures.BASELINE_UNSORTED_LOAD,
            ]:
                response = client.post(
                    "api/system-baseline/v1/baselines",
                    headers=fixtures.AUTH_HEADER,
                    json=baseline_load,
                )
                self.assertEqual(response.status_code, 200)

            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.baseline_ids = [b["id"] for b in result["data"]]
            self.assertEqual(len(self.baseline_ids), 3)

    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def tearDown(self, mock_fetch_systems):
        super(InternalApiBaselinesTests, self).tearDown()
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                # get systems for baseline
                response = client.get(
                    "api/system-baseline/v1/baselines/" + baseline["id"] + "/systems",
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

                system_ids = json.loads(response.content)

                # delete systems
                response = client.post(
                    "api/system-baseline/v1/baselines/"
                    + baseline["id"]
                    + "/systems/deletion_request",
                    headers=fixtures.AUTH_HEADER,
                    json=system_ids,
                )
                self.assertEqual(response.status_code, 200)

                # delete baseline
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_no_baselines_by_system_id(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            system_id = str(uuid.uuid4())

            response = client.get(
                "api/system-baseline/internal/v1/baselines",
                params={"system_id": system_id},
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_baseline_ids = json.loads(response.content)
            self.assertEqual(len(response_baseline_ids), 0)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_one_baseline_by_system_id(self, mock_fetch_systems):
        with self.client() as client:
            system_id = str(uuid.uuid4())
            mock_fetch_systems.return_value = [fixtures.a_system_with_profile(system_id)]
            baseline_ids = self.baseline_ids[0:1]

            for baseline_id in baseline_ids:
                response = client.post(
                    "api/system-baseline/v1/baselines/" + baseline_id + "/systems",
                    headers=fixtures.AUTH_HEADER,
                    json={"system_ids": [system_id]},
                )
                self.assertEqual(response.status_code, 200)

            response = client.get(
                "api/system-baseline/internal/v1/baselines",
                params={"system_id": system_id},
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_baseline_ids = json.loads(response.content)
            self.assertEqual(len(response_baseline_ids), len(baseline_ids))

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_few_baselines_by_system_id(self, mock_fetch_systems):
        with self.client() as client:
            system_id = str(uuid.uuid4())
            mock_fetch_systems.return_value = [fixtures.a_system_with_profile(system_id)]
            baseline_ids = self.baseline_ids[0:2]

            for baseline_id in baseline_ids:
                response = client.post(
                    "api/system-baseline/v1/baselines/" + baseline_id + "/systems",
                    headers=fixtures.AUTH_HEADER,
                    json={"system_ids": [system_id]},
                )
                self.assertEqual(response.status_code, 200)

            response = client.get(
                "api/system-baseline/internal/v1/baselines",
                params={"system_id": system_id},
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_baseline_ids = json.loads(response.content)
            self.assertEqual(len(response_baseline_ids), len(baseline_ids))


class ApiMappedSystemPatchTests(ApiTest):
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def setUp(self, mock_fetch_systems):
        super(ApiMappedSystemPatchTests, self).setUp()
        with self.client() as client:
            self.system_id = str(uuid.uuid4())
            mock_fetch_systems.return_value = [fixtures.a_system_with_profile(self.system_id)]

            # create a few baselines
            for i in range(1, 4):
                client.post(
                    "api/system-baseline/v1/baselines",
                    headers=fixtures.AUTH_HEADER,
                    json=fixtures.BASELINE_ONE_LOAD,
                )

            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.baseline_ids = [b["id"] for b in result["data"]]

            # create a mapped system associated with these baselines
            for baseline_id in self.baseline_ids:
                client.post(
                    "api/system-baseline/v1/baselines/" + baseline_id + "/systems",
                    headers=fixtures.AUTH_HEADER,
                    json={"system_ids": [self.system_id]},
                )

    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def tearDown(self, mock_fetch_systems):
        super(ApiMappedSystemPatchTests, self).tearDown()
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.a_system_with_profile(self.system_id)]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                # get systems for baseline
                response = client.get(
                    "api/system-baseline/v1/baselines/" + baseline["id"] + "/systems",
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

                system_ids = json.loads(response.content)

                # delete systems
                response = client.post(
                    "api/system-baseline/v1/baselines/"
                    + baseline["id"]
                    + "/systems/deletion_request",
                    headers=fixtures.AUTH_HEADER,
                    json=system_ids,
                )
                self.assertEqual(response.status_code, 200)

                # delete baseline
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    def test_update_mapped_system_with_groups(self):
        with self.client() as client:
            response = client.patch(
                "api/system-baseline/internal/v1/systems/" + self.system_id,
                json={
                    "groups": [
                        {"id": "new_group", "name": "new_group_name"},
                        {"id": "another_group", "name": "another_group_name"},
                    ]
                },
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            systems = SystemBaselineMappedSystem.query.where(
                SystemBaselineMappedSystem.system_id == self.system_id
            ).all()
            for system in systems:
                self.assertEqual(
                    system.groups,
                    [
                        {"id": "new_group", "name": "new_group_name"},
                        {"id": "another_group", "name": "another_group_name"},
                    ],
                )

    @unittest.skip("drift is being shut down")
    def test_update_mapped_system_without_groups(self):
        with self.client() as client:
            response = client.patch(
                "api/system-baseline/internal/v1/systems/" + self.system_id,
                json={},
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            systems = SystemBaselineMappedSystem.query.where(
                SystemBaselineMappedSystem.system_id == self.system_id
            ).all()
            for system in systems:
                self.assertEqual(system.groups, [])

    @unittest.skip("drift is being shut down")
    def test_update_mapped_system_with_other_data(self):
        with self.client() as client:
            response = client.patch(
                "api/system-baseline/internal/v1/systems/" + self.system_id,
                json={
                    "groups": [
                        {"id": "new_group", "name": "new_group_name"},
                        {"id": "another_group", "name": "another_group_name"},
                    ]
                },
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            systems = SystemBaselineMappedSystem.query.where(
                SystemBaselineMappedSystem.system_id == self.system_id
            ).all()
            for system in systems:
                self.assertEqual(
                    system.groups,
                    [
                        {"id": "new_group", "name": "new_group_name"},
                        {"id": "another_group", "name": "another_group_name"},
                    ],
                )

            # update mapped system with other data
            response = client.patch(
                "api/system-baseline/internal/v1/systems/" + self.system_id,
                json={"foo": "bar"},
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            # make sure it groups are not overwritten
            systems = SystemBaselineMappedSystem.query.where(
                SystemBaselineMappedSystem.system_id == self.system_id
            ).all()
            for system in systems:
                self.assertEqual(
                    system.groups,
                    [
                        {"id": "new_group", "name": "new_group_name"},
                        {"id": "another_group", "name": "another_group_name"},
                    ],
                )

    @unittest.skip("drift is being shut down")
    def test_update_not_existing_mapped_system(self):
        with self.client() as client:
            system_id = str(uuid.uuid4())
            response = client.patch(
                "api/system-baseline/internal/v1/systems/" + system_id,
                json={"groups": [{"id": "foo"}]},
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 404)
