from mimic_bench.datasets import load_events, load_ground_truth, load_companies, iter_ground_truth


def test_events_load():
    events = load_events()
    assert len(events) >= 10


def test_labels_load():
    gt = load_ground_truth()
    # flatten to a list of records
    records = [rec for event in gt.values() for rec in event.values()]
    assert len(records) >= 200


def test_label_schema():
    gt = load_ground_truth()
    records = [rec for event in gt.values() for rec in event.values()]
    required = {"event_id", "ticker", "actual_action_0_24h"}
    first = records[0]
    assert required.issubset(first.keys())


def test_companies_load():
    companies = load_companies()
    assert len(companies) >= 1
    assert "ticker" in companies[0]


def test_iter_ground_truth():
    records = list(iter_ground_truth())
    assert len(records) >= 200
