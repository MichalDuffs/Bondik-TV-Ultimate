# BTV-S01 — Service Directory v1

This is the eighteenth concrete Bondík City block.

The Directory Office creates one descriptive city map from the existing city
foundation and capability registry.

Protocol:

    bondik-city-service-directory/1

Contract:

    config/city-service-directory-contract.json

Builder:

    tools/city/service_directory.py

The directory joins buildings and virtual areas into locations and then maps
every registered capability to its exact location.

A location may come from a building, a virtual area, or both. Archive is both;
Control Tower is currently a virtual area.

The builder fails closed when a capability points to an unknown location or
when duplicate capability ids appear.

The directory is descriptive only. It does not grant execution, mutation,
network access, command authority, or agent authority.

Current exposure:

    execution = not-exposed
    mutation = not-allowed
    network = not-exposed

Verification:

    py tools/city/service_directory.py
    py -m pytest tools/checker/tests/test_city_service_directory.py -q
    py -m pytest tools/checker/tests -q

Architecture rule:

**the directory tells humans and machines what exists and where; permissions
remain a separate Gatehouse concern.**
