"""Protect existing runners when the optional dashboard is added."""

import json
import os
import shutil
import tempfile
import unittest
from importlib import import_module
from pathlib import Path
from unittest.mock import Mock, patch

from TwitchChannelPointsMiner import DashboardSettings, TwitchChannelPointsMiner
from TwitchChannelPointsMiner.classes.AnalyticsServer import AnalyticsServer
from TwitchChannelPointsMiner.classes.Settings import Settings
from TwitchChannelPointsMiner.classes.entities.Streamer import StreamerSettings
from TwitchChannelPointsMiner.logger import LoggerSettings

miner_module = import_module("TwitchChannelPointsMiner.TwitchChannelPointsMiner")
analytics_module = import_module("TwitchChannelPointsMiner.classes.AnalyticsServer")
ASSETS = Path(__file__).resolve().parents[1] / "assets"


class AnalyticsCompatibilityTest(unittest.TestCase):
    def miner(self):
        miner = object.__new__(TwitchChannelPointsMiner)
        miner.username = "tester"
        miner.logs_file = "logs/tester.log"
        return miner

    def test_legacy_network_host_and_parameter_units_are_preserved(self):
        server = Mock()
        with (
            patch.object(Settings, "enable_analytics", True, create=True),
            patch.object(
                analytics_module, "AnalyticsServer", return_value=server
            ) as factory,
            patch.object(TwitchChannelPointsMiner, "_start_dashboard") as dashboard,
        ):
            self.miner().analytics(host="0.0.0.0", port=8080, refresh=2, days_ago=30)
        factory.assert_called_once_with(
            host="0.0.0.0",
            port=8080,
            refresh=2,
            days_ago=30,
            username="tester",
            log_file_path="logs/tester.log",
        )
        self.assertTrue(server.daemon)
        self.assertEqual(server.name, "Analytics Thread")
        server.start.assert_called_once_with()
        dashboard.assert_not_called()

    def test_legacy_default_parameters_are_preserved(self):
        with (
            patch.object(Settings, "enable_analytics", True, create=True),
            patch.object(analytics_module, "AnalyticsServer") as factory,
        ):
            self.miner().analytics()
        factory.assert_called_once_with(
            host="127.0.0.1",
            port=5000,
            refresh=5,
            days_ago=7,
            username="tester",
            log_file_path="logs/tester.log",
        )

    def test_legacy_history_range_keeps_its_existing_upper_bound(self):
        with (
            patch.object(Settings, "enable_analytics", True, create=True),
            patch.object(analytics_module, "AnalyticsServer") as factory,
        ):
            self.miner().analytics(days_ago=100000)
        self.assertEqual(factory.call_args.kwargs["days_ago"], 365 * 15)

    def test_disabled_legacy_analytics_does_not_start_either_interface(self):
        with (
            patch.object(Settings, "enable_analytics", False, create=True),
            patch.object(analytics_module, "AnalyticsServer") as legacy,
            patch.object(TwitchChannelPointsMiner, "_start_dashboard") as dashboard,
            self.assertLogs(miner_module.logger, level="ERROR") as captured,
        ):
            self.miner().analytics(host="0.0.0.0")
        legacy.assert_not_called()
        dashboard.assert_not_called()
        self.assertIn("enable_analytics=True", captured.output[0])

    def test_legacy_routes_work_in_a_checkout_without_a_dashboard_build(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ASSETS, root / "assets")
            data_path = root / "analytics" / "tester"
            data_path.mkdir(parents=True)
            (data_path / "channel.json").write_text(
                json.dumps({"series": [{"x": 1, "y": 42, "z": "Watch"}]}),
                encoding="utf-8",
            )
            log_path = root / "logs" / "tester.log"
            log_path.parent.mkdir()
            log_path.write_text("Legacy log record", encoding="utf-8")
            try:
                os.chdir(root)
                miner = self.miner()
                miner.logs_file = str(log_path)
                with (
                    patch.object(Settings, "enable_analytics", True, create=True),
                    patch.object(
                        Settings, "analytics_path", str(data_path), create=True
                    ),
                    patch.object(AnalyticsServer, "start", autospec=True) as start,
                    patch.object(
                        TwitchChannelPointsMiner, "_start_dashboard"
                    ) as dashboard,
                    patch.object(analytics_module, "download_file") as download,
                ):
                    miner.analytics(host="0.0.0.0", refresh=2, days_ago=14)
                    start.assert_called_once()
                    # Exercise the actual legacy app without binding a network socket.
                    instance = start.call_args.args[0]
                    client = instance.app.test_client()
                    response = client.get("/")
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    self.assertIn('parseInt("120000")', html)
                    self.assertIn('parseInt("14")', html)
                    self.assertIn("/assets/script.js", html)
                    with client.get("/assets/script.js") as script:
                        self.assertEqual(script.status_code, 200)
                    self.assertEqual(
                        client.get("/json/channel").get_json()["series"][0]["y"], 42
                    )
                    self.assertEqual(
                        client.get("/streamers").get_json()[0]["name"], "channel.json"
                    )
                    self.assertEqual(
                        client.get("/log").get_data(as_text=True), "Legacy log record"
                    )
                    self.assertEqual(client.get("/api/v1/refresh").status_code, 404)
                    download.assert_not_called()
                    dashboard.assert_not_called()
            finally:
                os.chdir(previous)

    def test_dashboard_remains_explicitly_opt_in_for_existing_runners(self):
        cases = (
            (None, False, False),
            (None, True, False),
            (DashboardSettings(enabled=False), False, False),
            (DashboardSettings(), False, True),
        )
        previous = Path.cwd()
        for dashboard_settings, analytics_enabled, should_start in cases:
            with self.subTest(
                dashboard=dashboard_settings, analytics=analytics_enabled
            ), tempfile.TemporaryDirectory() as folder:
                try:
                    os.chdir(folder)
                    defaults = StreamerSettings(make_predictions=False)
                    with (
                        patch.multiple(
                            Settings,
                            enable_analytics=False,
                            analytics_path="unused",
                            logger=None,
                            streamer_settings=None,
                            use_hermes=True,
                            disable_ssl_cert_verification=False,
                            disable_at_in_nickname=False,
                            create=True,
                        ),
                        patch.object(
                            miner_module,
                            "internet_connection_available",
                            return_value=True,
                        ),
                        patch.object(miner_module, "Twitch") as twitch,
                        patch.object(
                            miner_module,
                            "configure_loggers",
                            return_value=("logs/tester.log", Mock()),
                        ),
                        patch.object(
                            miner_module,
                            "check_versions",
                            return_value=("2.2.0", "2.2.0"),
                        ),
                        patch.object(miner_module.signal, "signal"),
                        patch.object(
                            miner_module.WatchStreakCache,
                            "load_from_disk",
                            return_value=Mock(),
                        ),
                        patch.object(
                            TwitchChannelPointsMiner, "_load_daily_points_baseline"
                        ),
                        patch.object(
                            TwitchChannelPointsMiner, "_start_dashboard"
                        ) as start,
                        patch.object(analytics_module, "AnalyticsServer") as legacy,
                    ):
                        kwargs = (
                            {"dashboard_settings": dashboard_settings}
                            if dashboard_settings is not None
                            else {}
                        )
                        miner = TwitchChannelPointsMiner(
                            "tester",
                            enable_analytics=analytics_enabled,
                            streamer_settings=defaults,
                            logger_settings=LoggerSettings(),
                            **kwargs
                        )
                        if should_start:
                            start.assert_called_once_with(dashboard_settings)
                        else:
                            start.assert_not_called()
                        legacy.assert_not_called()
                        twitch.return_value.post_gql_request.assert_not_called()
                        self.assertIsNone(miner.dashboard_service)
                        self.assertFalse(
                            Path("logs/.state/dashboard.tester.sqlite3").exists()
                        )
                finally:
                    os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
