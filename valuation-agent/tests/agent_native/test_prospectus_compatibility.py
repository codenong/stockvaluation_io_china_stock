import subprocess
from pathlib import Path


def test_prospectus_compatibility_script_has_dry_run_report():
    repo_root = Path(__file__).parents[3]
    result = subprocess.run(
        [str(repo_root / "scripts/prospectus_compatibility.sh"), "--dry-run", "--limit", "15"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Prospectus Compatibility Report" in result.stdout
    assert "documents tested: 15" in result.stdout
    assert "extraction statuses:" in result.stdout
    assert "parser bugs fixed:" in result.stdout
    assert "fixtures added:" in result.stdout
    assert "final: DRY_RUN" in result.stdout


def test_prospectus_compatibility_script_uses_validator_supported_forms_only():
    repo_root = Path(__file__).parents[3]
    script = (repo_root / "scripts/prospectus_compatibility.sh").read_text(encoding="utf-8")

    assert 'PROSPECTUS_FORMS = ("S-1", "S-1/A", "424B3", "424B4", "424B5")' in script
    assert "form.startswith(\"424B\")" not in script
    assert "424B7" not in script


def test_prospectus_compatibility_script_checks_packet_substance_not_status_only():
    repo_root = Path(__file__).parents[3]
    script = (repo_root / "scripts/prospectus_compatibility.sh").read_text(encoding="utf-8")

    assert "packet_fact_count(packet)" in script
    assert "packet_issue_codes(packet)" in script
    assert "packet_is_valuation_ready(packet)" in script
    assert "empty_packet" in script
    assert "sourceClass" in script
    assert "provider" in script
    assert "sec-edgar-prospectus" in script


def test_prospectus_compatibility_script_checks_valuation_quality_gates():
    repo_root = Path(__file__).parents[3]
    script = (repo_root / "scripts/prospectus_compatibility.sh").read_text(encoding="utf-8")

    assert "derive_valuation_endpoint" in script
    assert "valuation_quality_gate" in script
    assert "valuationBasisStatus" in script
    assert "valuationCaseStatus" in script
    assert "pro_forma_cash_missing" in script
    assert "gross_proceeds_estimate_only" in script
    assert "clean_valuation_case" in script
    assert "quality gates exercised" in script
    assert "fallback_valuation_quality_gate" in script
    assert "reviewed_challenged_basis_packet" in script
