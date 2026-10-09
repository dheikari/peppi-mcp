"""Historical access evidence for immutable modes, never a current health check."""


def personal_access_readiness() -> dict:
    # Return new containers so a caller cannot mutate another response's evidence.
    return {
        "state": "live_mode_available",
        "live_data_verified": True,
        "live_data_verification_scope": "mcp_adapter",
        "live_data_checked_on": "2026-10-03",
        "is_current_health_check": False,
        "interactive_entry_url": "https://opiskelija-lay.peppi4.lapit.csc.fi/",
        "observed_browser_sign_in": {
            "method": "haka_shibboleth_saml_discovery",
            "checked_on": "2026-10-03",
            "verification_scope": "owner_completed_isolated_browser_sign_in",
            "is_current_health_check": False,
        },
        "observed_personal_ui": {
            "checked_on": "2026-10-03",
            "verification_scope": "owner_signed_in_read_only_inspection",
            "transcript_path": "/group/opiskelijan-tyopoyta-yo/suoritusote",
            "observed_components": [
                "study_right_menu",
                "separate_study_right_summaries",
                "completed_course_rows",
                "completed_only_filter",
            ],
            "completed_fields_reconciled_with_import": True,
            "repeated_page_read_verified": True,
            "is_current_health_check": False,
            "establishes_mcp_session": False,
        },
        "client_authentication": "explicit_connect_and_owner_completed_haka_in_disposable_firefox",
        "supported_personal_routes": ["browser_session_json_rights_and_rendered_transcript"],
        "missing_evidence": [
            "A supported third-party API contract or university automation guidance.",
            "Real cross-account switching and naturally expired/denied sessions; fictional tests are separate evidence.",
        ],
        "next_action": "Install the optional [live] extra, launch --mode live, and call connect_personal. Current synthetic/imported mode uses a fixed snapshot and has no authenticated connection.",
    }
