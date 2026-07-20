"""
Tests for restocking API endpoints.
"""
import pytest


class TestRestockRecommendationsEndpoint:
    """Test suite for restock recommendations endpoint."""

    def test_get_recommendations(self, client):
        """Test getting restock recommendations."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first_item = data[0]
        assert "sku" in first_item
        assert "name" in first_item
        assert "current_demand" in first_item
        assert "forecasted_demand" in first_item
        assert "shortfall" in first_item
        assert "recommended_quantity" in first_item
        assert "unit_cost" in first_item
        assert "line_total" in first_item
        assert "trend" in first_item

    def test_recommendations_only_positive_shortfall(self, client):
        """Test that all recommended items have a positive shortfall."""
        response = client.get("/api/restocking/recommendations")
        data = response.json()

        for item in data:
            assert item["shortfall"] > 0
            assert item["shortfall"] == item["forecasted_demand"] - item["current_demand"]

    def test_recommendations_sorted_by_shortfall_descending(self, client):
        """Test that recommendations are ranked by shortfall, highest first."""
        response = client.get("/api/restocking/recommendations")
        data = response.json()

        shortfalls = [item["shortfall"] for item in data]
        assert shortfalls == sorted(shortfalls, reverse=True)

    def test_recommendations_line_total_calculation(self, client):
        """Test that line_total matches recommended_quantity * unit_cost."""
        response = client.get("/api/restocking/recommendations")
        data = response.json()

        for item in data:
            calculated_total = item["recommended_quantity"] * item["unit_cost"]
            assert abs(item["line_total"] - calculated_total) < 0.01


class TestRestockOrderSubmission:
    """Test suite for submitting restocking orders."""

    def test_submit_restock_order(self, client):
        """Test submitting a valid restocking order."""
        response = client.post("/api/restocking/orders", json={
            "budget": 5000,
            "items": [
                {"sku": "WDG-001", "name": "Industrial Widget Type A", "quantity": 10, "unit_price": 45.0}
            ]
        })
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "Submitted"
        assert data["lead_time_days"] == 7
        assert abs(data["total_value"] - 450.0) < 0.01
        assert data["customer"] == "Internal Restocking"
        assert len(data["items"]) == 1

    def test_submit_restock_order_empty_items(self, client):
        """Test that submitting an order with no items is rejected."""
        response = client.post("/api/restocking/orders", json={
            "budget": 5000,
            "items": []
        })
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_submitted_order_visible_in_orders_list(self, client):
        """Test that a submitted restock order appears in GET /api/orders."""
        submit_response = client.post("/api/restocking/orders", json={
            "budget": 5000,
            "items": [
                {"sku": "BRG-102", "name": "Steel Bearing Assembly", "quantity": 5, "unit_price": 45.0}
            ]
        })
        assert submit_response.status_code == 200
        order_number = submit_response.json()["order_number"]

        orders_response = client.get("/api/orders?status=submitted")
        assert orders_response.status_code == 200
        orders = orders_response.json()

        assert any(o["order_number"] == order_number for o in orders)
        for order in orders:
            assert order["status"].lower() == "submitted"
