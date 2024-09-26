import datetime
import json
import unittest
import uuid

from urllib.parse import parse_qs, urlsplit

import mock

from kerlescan.exceptions import ItemNotReturned
from mock import patch

from system_baseline import app

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


class EmptyApiTests(ApiTest):
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_fetch_empty_baseline_list(self, mock_fetch_systems):
        mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
        with self.client() as client:
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["meta"]["count"], 0)


class BadUUIDTests(ApiTest):

    @unittest.skip("drift is being shut down")
    def test_delete_malformed_uuid(self):
        with self.client() as client:
            response = client.delete(
                "api/system-baseline/v1/baselines/MALFORMED-UUID",
                headers=fixtures.AUTH_HEADER,
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content)["message"],
            "malformed UUIDs requested (MALFORMED-UUID)",
        )


class InvalidFactsTests(ApiTest):
    @unittest.skip("drift is being shut down")
    def test_large_facts(self):
        large_factset = []
        for i in range(2**15):  # 32K
            large_factset.append({"name": str(i), "value": "lorem ipsum"})

        large_baseline = {
            "display_name": "large baseline",
            "baseline_facts": large_factset,
        }

        with self.client() as client:
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=large_baseline,
            )

        self.assertEqual(response.status_code, 400)

    @unittest.skip("drift is being shut down")
    def test_long_name_value(self):
        with self.client() as client:
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_LONG_NAME_LOAD,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "is over 500 characters",
                response.content.decode("utf-8"),
            )

            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_LONG_VALUE_LOAD,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "is over 1000 characters",
                response.content.decode("utf-8"),
            )


class ApiSortTests(ApiTest):
    def setUp(self):
        super(ApiSortTests, self).setUp()
        with self.client() as client:
            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_UNSORTED_LOAD,
            )

    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def tearDown(self, mock_fetch_systems):
        with self.client() as client:
            super(ApiSortTests, self).tearDown()
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_fetch_sorted_baseline_facts(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result["meta"]["count"], 1)
            response = client.get(
                "api/system-baseline/v1/baselines/%s" % result["data"][0]["id"],
                headers=fixtures.AUTH_HEADER,
            )
            result = json.loads(response.content)
            # confirm that we get sorted names back, including nested names
            self.assertEqual(
                result["data"][0]["baseline_facts"],
                [
                    {"name": "A-name", "value": "64GB"},
                    {
                        "name": "B-name",
                        "values": [
                            {"name": "a-nested_cpu_sockets", "value": "32"},
                            {"name": "b-nested_cpu_sockets", "value": "32"},
                            {"name": "Z-nested_cpu_sockets", "value": "32"},
                        ],
                    },
                    {"name": "C-name", "value": "128GB"},
                    {"name": "D-name", "value": "16"},
                ],
            )


class ApiGeneralTests(ApiTest):
    def setUp(self):
        super(ApiGeneralTests, self).setUp()
        with self.client() as client:
            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_ONE_LOAD,
            )
            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_TWO_LOAD,
            )

    def tearDown(self):
        super(ApiGeneralTests, self).tearDown()
        with self.client() as client:
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_value_values(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_VALUE_VALUES_LOAD,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "fact arch cannot have value and values defined",
                response.content.decode("utf-8"),
            )

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_fetch_baseline_list(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result["meta"]["count"], 2)
            self.assertEqual(result["meta"]["total_available"], 2)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_fetch_baselines_missing_uuid(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            existing_id = result["data"][0]["id"]
            missing_id = str(uuid.uuid4())
            response = client.get(
                f"api/system-baseline/v1/baselines/{existing_id},{missing_id}",
                headers=fixtures.AUTH_HEADER,
            )
            result = json.loads(response.content)
            self.assertEqual(response.status_code, 404)
            message = json.loads(response.content)["message"]
            self.assertEqual(f"ids [{missing_id}] not available to display", message)

    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_fetch_baseline_list_sort_display_name(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get(
                "api/system-baseline/v1/baselines?order_by=display_name",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            asc_result = json.loads(response.content)
            response = client.get(
                "api/system-baseline/v1/baselines?order_by=display_name&order_how=DESC",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            desc_result = json.loads(response.content)
            # check that the ascending result is the inverse of the descending result
            self.assertEqual(desc_result["data"][::-1], asc_result["data"])

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_create_deletion_request(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            ids_to_delete = [b["id"] for b in result["data"]]
            response = client.post(
                "api/system-baseline/v1/baselines/deletion_request",
                headers=fixtures.AUTH_HEADER,
                json={"baseline_ids": ids_to_delete},
            )
            self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_fetch_baseline_list_sort_updated(self, mock_fetch_systems):
        with self.client() as client:
            # modify one baseline
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            uuid_to_modify = json.loads(response.content)["data"][0]["id"]
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % uuid_to_modify,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_TOUCH,
            )
            self.assertEqual(response.status_code, 200)
            # ensure modified baseline is in the right place of the sort
            response = client.get(
                "api/system-baseline/v1/baselines?order_by=updated",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            asc_result = json.loads(response.content)
            self.assertEqual(asc_result["data"][1]["id"], uuid_to_modify)

            response = client.get(
                "api/system-baseline/v1/baselines?order_by=updated&order_how=DESC",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            desc_result = json.loads(response.content)
            # check that the ascending result is the inverse of the descending result
            self.assertEqual(desc_result["data"][::-1], asc_result["data"])

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_fetch_duplicate_uuid(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get(
                "api/system-baseline/v1/baselines?display_name=arch",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            uuid = result["data"][0]["id"]
            response = client.get(
                "api/system-baseline/v1/baselines/%s,%s" % (uuid, uuid),
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 400)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_fetch_baseline_search(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get(
                "api/system-baseline/v1/baselines?display_name=arch",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result["meta"]["count"], 1)
            self.assertEqual(result["meta"]["total_available"], 2)
            self.assertEqual(result["data"][0]["display_name"], "arch baseline")

            response = client.get(
                "api/system-baseline/v1/baselines?display_name= ",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result["meta"]["count"], 2)

            response = client.get(
                "api/system-baseline/v1/baselines?display_name=a_ch",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result["meta"]["count"], 0)

            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_UNDERSCORE_LOAD,
            )
            self.assertEqual(response.status_code, 200)

            response = client.get(
                "api/system-baseline/v1/baselines?display_name=has_an_underscore",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result["meta"]["count"], 1)


class ApiErrorHTTPTests(ApiTest):
    def setUp(self):
        super(ApiErrorHTTPTests, self).setUp()

    def tearDown(self):
        super(ApiErrorHTTPTests, self).tearDown()

    @unittest.skip("drift is being shut down")
    def test_baselines_wrong_uuid(self):
        test_uuids = [
            (
                "ed877dfc-14e9-4ccf-ba3d-68d9ff34645",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "ed877dfc-14e9-4ccf-ba3d-68d9ff3464571",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "-ed877dfc-14e9-4ccf-ba3d-68d9ff34645",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "{ed877dfc-14e9-4ccf-ba3d-68d9ff346455",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "{ed877dfc-14e9-4ccf-ba3d-68d9ff346455",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "ed877dfc-14e9-4ccf-ba3d-68d9ff346457-",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                " ed877dfc-14e9-4ccf-ba3d-68d9ff34645",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "!ed877dfc-14e9-4ccf-ba3d-68d9ff34645",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "@ed877dfc-14e9-4ccf-ba3d-68d9ff34645",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                ">ed877dfc-14e9-4ccf-ba3d-68d9ff34645",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "<ed877dfc-14e9-4ccf-ba3d-68d9ff34645",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                "(ed877dfc-14e9-4ccf-ba3d-68d9ff34645",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                r"!@#`~$-%^&*-*()--+=[]-{}\/<>?|645764",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                r"!@#`~$-%^&*-*()--+=[]-{}\/<>?|6457635",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
            (
                r"!@#`~$-%^&*-*()--+=[]-{}\/<>?|64573",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 400, 400],
            ),
        ]

        for test_uuid in test_uuids:
            endpoint = "/baselines/" + test_uuid[0]
            http_methods = test_uuid[1]
            expected_status_codes = test_uuid[2]

            for http_method in http_methods:
                expected_status_code = expected_status_codes.pop(0)
                with self.subTest(
                    endpoint=endpoint, method=http_method, expected_status_code=expected_status_code
                ):
                    with self.client() as client:
                        response = client.request(
                            http_method,
                            f"api/system-baseline/v1{endpoint}",
                            headers=fixtures.AUTH_HEADER,
                        )
                        self.assertEqual(response.status_code, expected_status_code)

    def test_baselines_wrong_url(self):
        api_endpoints = [
            ("/baseline", ["GET", "POST", "PATCH", "DELETE"], [404, 404, 404, 404]),
            ("/baselines/", ["GET", "POST", "PATCH", "DELETE"], [200, 400, 405, 405]),
            ("/!baselines", ["GET", "POST", "PATCH", "DELETE"], [404, 404, 404, 404]),
            ("/?baselines", ["GET", "POST", "PATCH", "DELETE"], [404, 404, 404, 404]),
            ("/{baselines}", ["GET", "POST", "PATCH", "DELETE"], [404, 404, 404, 404]),
            ("/-baselines", ["GET", "POST", "PATCH", "DELETE"], [404, 404, 404, 404]),
            ("/baselines-", ["GET", "POST", "PATCH", "DELETE"], [404, 404, 404, 404]),
            ("/&baselines-", ["GET", "POST", "PATCH", "DELETE"], [404, 404, 404, 404]),
            ("/~baselines", ["GET", "POST", "PATCH", "DELETE"], [404, 404, 404, 404]),
            (
                "/baselines/?ed877dfc-14e9-4ccf-ba3d-68d9ff346457",
                ["GET", "POST", "PATCH", "DELETE"],
                [400, 400, 405, 405],
            ),
            (
                "/baselines/#ed877dfc-14e9-4ccf-ba3d-68d9ff346457",
                ["GET", "POST", "PATCH", "DELETE"],
                [200, 400, 405, 405],
            ),
        ]

        for api_endpoint in api_endpoints:
            endpoint = api_endpoint[0]
            http_methods = api_endpoint[1]
            expected_status_codes = api_endpoint[2]

            for http_method in http_methods:
                expected_status_code = expected_status_codes.pop(0)
                with self.subTest(
                    endpoint=endpoint, method=http_method, expected_status_code=expected_status_code
                ):
                    with self.client() as client:
                        response = client.request(
                            http_method,
                            f"api/system-baseline/v1{endpoint}",
                            headers=fixtures.AUTH_HEADER,
                        )
                        self.assertEqual(response.status_code, expected_status_code)


class CopyBaselineTests(ApiTest):
    def setUp(self):
        super(CopyBaselineTests, self).setUp()
        with self.client() as client:
            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_ONE_LOAD,
            )
            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_TWO_LOAD,
            )

    def tearDown(self):
        super(CopyBaselineTests, self).tearDown()
        with self.client() as client:
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_copy_baseline(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            source_uuid = result["data"][0]["id"]

            response = client.post(
                "api/system-baseline/v1/baselines/%s?display_name=" % source_uuid,
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 400)

            response = client.post(
                "api/system-baseline/v1/baselines/%s?display_name=copy" % source_uuid,
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            copied_baseline = json.loads(response.content)

            response = client.post(
                "api/system-baseline/v1/baselines/%s?display_name=copy" % source_uuid,
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 400)

            response = client.get(
                "api/system-baseline/v1/baselines/%s" % source_uuid,
                headers=fixtures.AUTH_HEADER,
            )
            original_baseline = json.loads(response.content)

            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content)["meta"]["count"], 3)

            old_date = datetime.datetime.strptime(
                original_baseline["data"][0]["created"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            new_date = datetime.datetime.strptime(
                copied_baseline["created"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            self.assertNotEqual(old_date, new_date)


class ApiPatchTests(ApiTest):
    def setUp(self):
        super(ApiPatchTests, self).setUp()
        with self.client() as client:
            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_THREE_LOAD,
            )

    def tearDown(self):
        super(ApiPatchTests, self).tearDown()
        with self.client() as client:
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_patch_baseline(self, mock_fetch_systems):
        with self.client() as client:
            # obtain the UUID for a baseline
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            patched_uuid = result["data"][0]["id"]

            # apply patch to data
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PATCH,
            )
            self.assertEqual(response.status_code, 200)

            # confirm patch landed
            response = client.get(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
            )
            result = json.loads(response.content)
            for fact in result["data"][0]["baseline_facts"]:
                self.assertTrue(fact["name"] in ("nested", "nested fact 2"))

            # create a second baseline
            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_ONE_LOAD,
            )
            # attempt to rename the first baseline to the second
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PARTIAL_CONFLICT,
            )
            self.assertEqual(response.status_code, 400)

            # attempt to use an empty fact name
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PATCH_EMPTY_NAME,
            )
            self.assertIn("fact name cannot be empty", response.content.decode("utf-8"))
            self.assertEqual(response.status_code, 400)

            # attempt to use an empty fact value
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PATCH_EMPTY_VALUE,
            )
            self.assertIn(
                "value for cpu_sockets_renamed cannot be empty",
                response.content.decode("utf-8"),
            )
            # attempt to rename the baseline to a bad name
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PATCH_LONG_NAME,
            )
            self.assertEqual(response.status_code, 400)

            # attempt to add a fact with leading whitespace
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PATCH_LEADING_WHITESPACE_NAME,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "Fact name cannot have leading or trailing whitespace.",
                response.content.decode("utf-8"),
            )

            # attempt to add a fact with trailing whitespace
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PATCH_TRAILING_WHITESPACE_NAME,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "Fact name cannot have leading or trailing whitespace.",
                response.content.decode("utf-8"),
            )

            # attempt to add a value with leading whitespace
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PATCH_LEADING_WHITESPACE_VALUE,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "Value for cpu_sockets_renamed cannot have leading or trailing whitespace.",
                response.content.decode("utf-8"),
            )

            # attempt to add a value with trailing whitespace
            response = client.patch(
                "api/system-baseline/v1/baselines/%s" % patched_uuid,
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_PATCH_TRAILING_WHITESPACE_VALUE,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "Value for cpu_sockets_renamed cannot have leading or trailing whitespace.",
                response.content.decode("utf-8"),
            )


class CreateFromInventoryTests(ApiTest):
    def tearDown(self):
        with self.client() as client:
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)
        super(CreateFromInventoryTests, self).tearDown()

    @unittest.skip("drift is being shut down")
    @patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_create_from_inventory(self, mock_fetch):
        with self.client() as client:
            mock_fetch.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.CREATE_FROM_INVENTORY,
            )
            self.assertEqual(response.status_code, 200)

            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.CREATE_FROM_INVENTORY_LONG_NAME,
            )
            self.assertEqual(response.status_code, 400)

    @unittest.skip("drift is being shut down")
    @patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_create_from_inventory_not_found(self, mock_fetch):
        with self.client() as client:
            mock_fetch.side_effect = ItemNotReturned("not found!")
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.CREATE_FROM_INVENTORY,
            )
            self.assertEqual(response.status_code, 404)
            self.assertIn(
                "inventory UUID df925152-c45d-11e9-a1f0-c85b761454fa not available",
                response.content.decode("utf-8"),
            )

    @unittest.skip("drift is being shut down")
    def test_create_from_inventory_bad_uuid(self):
        with self.client() as client:
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.CREATE_FROM_INVENTORY_MALFORMED_UUID,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("malformed UUIDs requested", response.content.decode("utf-8"))


class ApiDuplicateTests(ApiTest):
    def tearDown(self):
        with self.client() as client:
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
            self.assertEqual(response.status_code, 200)
        super(ApiDuplicateTests, self).tearDown()

    @unittest.skip("drift is being shut down")
    def test_duplicate_baseline(self):
        with self.client() as client:
            response = client.post(
                "/api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_DUPLICATES_LOAD,
            )
            self.assertIn(
                "A fact with this name already exists.",
                response.content.decode("utf-8"),
            )

            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_DUPLICATES_TWO_LOAD,
            )
            self.assertIn("A fact with this name already exists.", response.content.decode("utf-8"))

            # test that a category and fact can have the same name
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_DUPLICATES_THREE_LOAD,
            )
            self.assertEqual(response.status_code, 200)

    @unittest.skip("drift is being shut down")
    def test_create_baseline_with_leading_trailing_whitespace(self):
        with self.client() as client:
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_NAME_LEADING_WHITESPACE,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "Baseline name cannot have leading or trailing whitespace.",
                response.content.decode("utf-8"),
            )

            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_NAME_TRAILING_WHITESPACE,
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn(
                "Baseline name cannot have leading or trailing whitespace.",
                response.content.decode("utf-8"),
            )


class ApiPaginationTests(ApiTest):
    def setUp(self):
        super(ApiPaginationTests, self).setUp()
        with self.client() as client:
            self.display_name = fixtures.BASELINE_TWO_LOAD["display_name"]
            client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_TWO_LOAD,
            )

    def tearDown(self):
        super(ApiPaginationTests, self).tearDown()
        with self.client() as client:
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            data = json.loads(response.content)["data"]
            for baseline in data:
                response = client.delete(
                    "api/system-baseline/v1/baselines/%s" % baseline["id"],
                    headers=fixtures.AUTH_HEADER,
                )
                self.assertEqual(response.status_code, 200)

    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_links_with_additional_query_param(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get(
                "api/system-baseline/v1/baselines",
                params={"display_name": self.display_name},
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            links = json.loads(response.content)["links"]
            for link_name in ("first", "next", "previous", "last"):
                self.assertIn(link_name, links)
                split_parts = urlsplit(links[link_name])
                query_params = parse_qs(split_parts[3])
                self.assertIn("display_name", query_params)
                self.assertEqual(query_params["display_name"][0], self.display_name)


class ApiSystemsAssociationTests(ApiTest):
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def setUp(self, mock_fetch_systems):
        super(ApiSystemsAssociationTests, self).setUp()

        self.system_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ]

        self.system_groupings = [
            [
                {"id": "d6bba69a-25a8-11e9-81b8-c85b761454fa", "name": "first group"},
            ],
            [
                {"id": "11b3cbce-25a9-11e9-8457-c85b761454fa", "name": "second group"},
            ],
            [
                {"id": "d6bba69a-25a8-11e9-81b8-c85b761454fa", "name": "first group"},
            ],
            [
                {"id": "d6bba69a-25a8-11e9-81b8-c85b761454fa", "name": "first group"},
                {"id": "11b3cbce-25a9-11e9-8457-c85b761454fa", "name": "second group"},
            ],
            [],
        ]

        mock_fetch_systems.return_value = [
            {
                **fixtures.SYSTEM_WITH_PROFILE,
                "id": system_id,
                "groups": self.system_groupings[index],
            }
            for index, system_id in enumerate(self.system_ids)
        ]

        with self.client() as client:
            response = client.post(
                "api/system-baseline/v1/baselines",
                headers=fixtures.AUTH_HEADER,
                json=fixtures.BASELINE_ONE_LOAD,
            )
            self.assertEqual(response.status_code, 200)

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
            # get all baselines
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            baselines = json.loads(response.content)["data"]

            for baseline in baselines:
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
    def test_list_systems_with_baseline(self):
        with self.client() as client:
            response = client.get(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]
            self.assertEqual(len(response_system_ids), 5)

            for system_id in self.system_ids:
                self.assertIn(system_id, response_system_ids)

    @unittest.skip("drift is being shut down")
    def test_list_systems_with_baseline_and_inventory_group_ids_filter(self):
        with self.client() as client:
            response = client.get(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems"
                "?group_ids[]=d6bba69a-25a8-11e9-81b8-c85b761454fa"
                "&group_ids[]=11b3cbce-25a9-11e9-8457-c85b761454fa",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]
            self.assertEqual(len(response_system_ids), 4)

    @unittest.skip("drift is being shut down")
    def test_list_systems_with_baseline_and_inventory_group_names_filter(self):
        with self.client() as client:
            response = client.get(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems"
                "?group_names[]=first%20group"
                "&group_names[]=second%20group",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]
            self.assertEqual(len(response_system_ids), 4)

    @unittest.skip("drift is being shut down")
    def test_list_systems_with_baseline_and_inventory_group_ids_and_names_filter(self):
        with self.client() as client:
            response = client.get(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems"
                "?group_names[]=first%20group"
                "&group_names[]=second%20group"
                "&group_ids[]=11b3cbce-25a9-11e9-8457-c85b761454fa",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]
            self.assertEqual(len(response_system_ids), 4)

    @unittest.skip("drift is being shut down")
    def test_list_systems_with_baseline_and_inventory_group_filter_non_grouped(self):
        with self.client() as client:
            response = client.get(
                "api/system-baseline/v1/baselines/" + self.baseline_id + "/systems"
                "?group_ids[]="
                "&group_ids[]=11b3cbce-25a9-11e9-8457-c85b761454fa",
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)

            response_system_ids = json.loads(response.content)["system_ids"]
            self.assertEqual(len(response_system_ids), 3)

    @unittest.skip("drift is being shut down")
    def test_delete_systems_with_baseline(self):
        # to delete
        system_ids = [
            self.system_ids[0],
            self.system_ids[1],
        ]

        system_ids_param = ",".join(system_ids)

        with self.client() as client:
            # delete systems
            response = client.delete(
                "api/system-baseline/v1/baselines/"
                + self.baseline_id
                + "/systems/%s" % system_ids_param,
                headers=fixtures.AUTH_HEADER,
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
    def test_delete_systems_with_baseline_deletion_request(self):
        # to delete
        system_ids = [
            self.system_ids[0],
            self.system_ids[1],
        ]

        with self.client() as client:
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
        # to delete
        system_ids = [
            str(uuid.uuid4()),
        ]

        with self.client() as client:
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
            self.assertEqual(len(response_system_ids), 5)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_adding_few_systems(self, mock_fetch_systems):
        # to create
        system_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ]

        with self.client() as client:
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
            self.assertEqual(len(response_system_ids), 7)

            for system_id in system_ids:
                self.assertIn(system_id, response_system_ids)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_get_system_count_for_baselines(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result["data"][0]["mapped_system_count"], 5)

    @unittest.skip("drift is being shut down")
    @mock.patch("system_baseline.views.v1.fetch_systems_with_profiles")
    def test_get_system_count_for_baselines_by_ids(self, mock_fetch_systems):
        with self.client() as client:
            mock_fetch_systems.return_value = [fixtures.SYSTEM_WITH_PROFILE]
            response = client.get("api/system-baseline/v1/baselines", headers=fixtures.AUTH_HEADER)
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            baseline_uuid = result["data"][0]["id"]  # get one existing baseline for the actual test

            response = client.get(
                "api/system-baseline/v1/baselines/%s" % baseline_uuid,
                headers=fixtures.AUTH_HEADER,
            )
            self.assertEqual(response.status_code, 200)
            result = json.loads(response.content)
            self.assertEqual(result["data"][0]["mapped_system_count"], 5)
