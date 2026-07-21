"""Tests for deterministic candidate application destination resolution."""

from ijobs_scraper.application_destination import (
    is_safe_application_destination,
    resolve_application_destination,
)

SOURCE_URL = "https://www.myjobmag.co.ke/job/pastry-sous-chef-emerge-egress-consulting"


def test_builds_mailto_from_email_and_job_title() -> None:
    destination = resolve_application_destination(
        application_instructions=(
            "Interested candidates should forward their CV to "
            "careers@emergeegressconsulting.com using the position as subject."
        ),
        source_url=SOURCE_URL,
        job_title="Pastry Sous Chef Role",
    )

    assert destination == (
        "mailto:careers@emergeegressconsulting.com?subject=Pastry%20Sous%20Chef%20Role"
    )


def test_preserves_safe_explicit_mailto() -> None:
    destination = resolve_application_destination(
        application_instructions="Apply via mailto:jobs@example.com?subject=Sous%20Chef",
        source_url=SOURCE_URL,
        job_title="Pastry Sous Chef Role",
    )

    assert destination == "mailto:jobs@example.com?subject=Sous%20Chef"


def test_returns_explicit_employer_application_url() -> None:
    destination = resolve_application_destination(
        application_instructions="Apply at https://careers.example.com/jobs/sous-chef.",
        source_url=SOURCE_URL,
        job_title="Pastry Sous Chef Role",
    )

    assert destination == "https://careers.example.com/jobs/sous-chef"


def test_resolves_bare_employer_domain_from_myjobmag_instructions() -> None:
    destination = resolve_application_destination(
        application_instructions=(
            "Interested and qualified? Go to SevenTwenty Holdings Ltd on "
            "seventwentyholdings.co.ke to apply"
        ),
        source_url=SOURCE_URL,
        job_title="Procurement & Inventory Coordinator",
    )

    assert destination == "https://seventwentyholdings.co.ke"


def test_never_returns_the_scraper_source_url() -> None:
    destination = resolve_application_destination(
        application_instructions=f"Apply at {SOURCE_URL}",
        source_url=SOURCE_URL,
        job_title="Pastry Sous Chef Role",
    )

    assert destination is None


def test_rejects_www_variant_and_source_subdomain() -> None:
    assert not is_safe_application_destination(
        "https://myjobmag.co.ke/job/another-role",
        source_url=SOURCE_URL,
    )
    assert not is_safe_application_destination(
        "https://apply.myjobmag.co.ke/job/another-role",
        source_url="https://myjobmag.co.ke/jobs",
    )


def test_rejects_unsafe_or_missing_destinations() -> None:
    assert not is_safe_application_destination(
        "javascript:alert(1)",
        source_url=SOURCE_URL,
    )
    assert not is_safe_application_destination(
        "mailto:jobs@example.com?subject=Role%0ABcc:attacker@example.com",
        source_url=SOURCE_URL,
    )
    assert not is_safe_application_destination(
        "http://https://forms.gle/RaUGVUsohVSQ9Cfi8",
        source_url=SOURCE_URL,
    )
    assert (
        resolve_application_destination(
            application_instructions="Applications are now closed.",
            source_url=SOURCE_URL,
            job_title="Pastry Sous Chef Role",
        )
        is None
    )
