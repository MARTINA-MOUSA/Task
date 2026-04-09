"""Embedded knowledge base for customers, packages, and rules."""

from __future__ import annotations


CUSTOMERS = {
    "A": {
        "industry": "Healthcare",
        "region": "Riyadh",
        "employees": 120,
        "dependents_ratio": 0.60,
        "budget": "Medium",
        "priority": "Balanced coverage and network strength",
    },
    "B": {
        "industry": "Construction",
        "region": "Jeddah",
        "employees": 80,
        "dependents_ratio": 0.30,
        "budget": "Low",
        "priority": "Cheapest acceptable option",
    },
    "C": {
        "industry": "Retail",
        "region": "Dammam",
        "employees": 200,
        "dependents_ratio": 0.50,
        "budget": "Medium",
        "priority": "Stable service and moderate cost",
    },
}


PACKAGES = {
    "Basic": {
        "network": "C",
        "price_min": 4000,
        "price_max": 5000,
        "coverage": "Low",
        "notes": "Cheapest option, limited provider access",
    },
    "Standard": {
        "network": "B",
        "price_min": 6000,
        "price_max": 7500,
        "coverage": "Medium",
        "notes": "Balanced price and network",
    },
    "Premium": {
        "network": "A",
        "price_min": 9000,
        "price_max": 12000,
        "coverage": "High",
        "notes": "Best coverage and strongest network",
    },
}


RULES = {
    "industry_risk": {
        "Healthcare": "high",
        "Construction": "medium",
        "Retail": "medium-low",
    },
    "region_cost": {
        "Riyadh": "high",
        "Jeddah": "moderate",
        "Dammam": "moderate-to-high",
    },
    "budget_limits": {
        "Low": ["Basic", "Standard"],
        "Medium": ["Basic", "Standard", "Premium"],
        "High": ["Standard", "Premium"],
    },
    "dependents_note": "High dependents ratio (>0.5) increases cost pressure and benefit control needs",
}

