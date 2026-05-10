"""Unit tests validating preset scenario data and customer profile completeness."""

from src.frontend.scenarios import (
    CATEGORIES,
    CUSTOMER_PROFILES,
    SCENARIOS,
    SCENARIOS_BY_CATEGORY,
    CustomerProfile,
    PresetScenario,
)


class TestScenarioCount:
    def test_at_least_9_scenarios(self):
        assert len(SCENARIOS) >= 9

    def test_at_least_3_categories(self):
        assert len(CATEGORIES) >= 3

    def test_at_least_3_scenarios_per_category(self):
        for category, items in SCENARIOS_BY_CATEGORY.items():
            assert len(items) >= 3, f"Category '{category}' has fewer than 3 scenarios"

    def test_billing_category_exists(self):
        assert "Billing" in CATEGORIES

    def test_technical_category_exists(self):
        assert "Technical" in CATEGORIES

    def test_account_category_exists(self):
        assert "Account" in CATEGORIES


class TestScenarioFields:
    def test_all_scenarios_have_required_fields(self):
        for scenario in SCENARIOS:
            assert isinstance(scenario, PresetScenario)
            assert scenario.id, f"Scenario missing id: {scenario}"
            assert scenario.category, f"Scenario missing category: {scenario.id}"
            assert scenario.title, f"Scenario missing title: {scenario.id}"
            assert scenario.query_text, f"Scenario missing query_text: {scenario.id}"
            assert scenario.description, f"Scenario missing description: {scenario.id}"

    def test_scenario_ids_are_unique(self):
        ids = [s.id for s in SCENARIOS]
        assert len(ids) == len(set(ids)), "Duplicate scenario IDs found"

    def test_query_texts_are_non_empty_strings(self):
        for scenario in SCENARIOS:
            assert isinstance(scenario.query_text, str)
            assert len(scenario.query_text.strip()) > 0


class TestScenariosByCategoryMapping:
    def test_scenarios_by_category_covers_all_scenarios(self):
        total = sum(len(v) for v in SCENARIOS_BY_CATEGORY.values())
        assert total == len(SCENARIOS)

    def test_scenarios_by_category_keys_match_categories(self):
        assert set(SCENARIOS_BY_CATEGORY.keys()) == set(CATEGORIES)


class TestCustomerProfiles:
    def test_at_least_3_customer_profiles(self):
        assert len(CUSTOMER_PROFILES) >= 3

    def test_all_profiles_have_required_fields(self):
        for profile in CUSTOMER_PROFILES:
            assert isinstance(profile, CustomerProfile)
            assert profile.id, f"Profile missing id: {profile}"
            assert profile.name, f"Profile missing name: {profile.id}"
            assert profile.description, f"Profile missing description: {profile.id}"

    def test_profile_ids_are_unique(self):
        ids = [p.id for p in CUSTOMER_PROFILES]
        assert len(ids) == len(set(ids)), "Duplicate profile IDs found"

    def test_expected_customer_ids_present(self):
        ids = {p.id for p in CUSTOMER_PROFILES}
        assert "cust-001" in ids
        assert "cust-002" in ids
        assert "cust-003" in ids
