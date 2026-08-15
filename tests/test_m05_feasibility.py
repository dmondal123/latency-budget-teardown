from scripts.m05_feasibility import assess_condition, cache_correctness_reasons, has_sustained_swap, make_image_fixtures, summary_status


def test_assess_condition_accepts_bounded_metal_run():
    result = assess_condition(
        device="Device(gpu, 0)",
        server_log="Metal worker initialized",
        request_results=[{"ok": True}, {"ok": True}],
        memory_samples=[
            {"rss_bytes": 12 * 1024**3, "swap_used_bytes": 0},
            {"rss_bytes": 18 * 1024**3, "swap_used_bytes": 0},
        ],
        capacity_bytes=24 * 1024**3,
        safety_margin_bytes=4 * 1024**3,
        sustained_swap_bytes=64 * 1024**2,
    )

    assert result == {"status": "pass", "reasons": []}


def test_assess_condition_rejects_cpu_swap_and_memory_pressure():
    result = assess_condition(
        device="Device(cpu, 0)",
        server_log="server started without Metal",
        request_results=[{"ok": False, "error": "timeout"}],
        memory_samples=[
            {"rss_bytes": 19 * 1024**3, "swap_used_bytes": 0},
            {"rss_bytes": 21 * 1024**3, "swap_used_bytes": 128 * 1024**2},
            {"rss_bytes": 21 * 1024**3, "swap_used_bytes": 256 * 1024**2},
        ],
        capacity_bytes=24 * 1024**3,
        safety_margin_bytes=4 * 1024**3,
        sustained_swap_bytes=64 * 1024**2,
    )

    assert result["status"] == "fail"
    assert {"device_is_not_gpu", "metal_worker_not_observed", "request_failed", "memory_headroom_exceeded", "sustained_swap"} <= set(result["reasons"])


def test_sustained_swap_requires_two_consecutive_material_increases():
    mib = 1024**2
    assert not has_sustained_swap([0, 80 * mib, 80 * mib], 64 * mib)
    assert has_sustained_swap([0, 80 * mib, 160 * mib], 64 * mib)


def test_image_fixtures_have_distinct_expected_identities():
    fixtures = make_image_fixtures()

    assert fixtures["black"]["expected_color"] == "black"
    assert fixtures["red"]["expected_color"] == "red"
    assert fixtures["black"]["data_url"] != fixtures["red"]["data_url"]


def test_cache_correctness_requires_parity_and_distinct_image_identity():
    enabled = [{"ok": True, "output": "READY"}, {"ok": True, "output": "black"}, {"ok": True, "output": "red"}]
    disabled = [{"ok": True, "output": "READY"}, {"ok": True, "output": "black"}, {"ok": True, "output": "red"}]

    assert cache_correctness_reasons(enabled, disabled) == []
    assert "image_identity_failed" in cache_correctness_reasons([enabled[0], enabled[1], {"ok": True, "output": "black"}], disabled)
    assert "cache_output_parity_failed" in cache_correctness_reasons(enabled, [{**item, "output": "different"} for item in disabled])


def test_summary_accepts_a_safe_lower_fraction_while_retaining_higher_failure():
    records = [
        {"name": "memory_fraction_0.60", "acceptance": {"status": "pass"}},
        {"name": "memory_fraction_0.80", "acceptance": {"status": "fail"}},
        {"name": "cache_enabled", "acceptance": {"status": "pass"}},
        {"name": "cache_disabled", "acceptance": {"status": "pass"}},
        {"name": "concurrency_2", "acceptance": {"status": "pass"}},
        {"name": "concurrency_4", "acceptance": {"status": "pass"}},
    ]

    assert summary_status(records, selected_fraction=0.60) == "pass"
