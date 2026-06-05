package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.SourceProvenance;

import java.util.ArrayList;
import java.util.List;

public final class ProspectusTestPackets {

    private ProspectusTestPackets() {
    }

    public static ProspectusFinancialPacket reviewedPacket() {
        SourceProvenance provenance = SourceProvenance.primaryFiling(
                "sec-edgar-prospectus",
                "2026-06-03",
                "2025-12-31");

        ProspectusFinancialPacket packet = new ProspectusFinancialPacket();
        packet.setSchemaVersion("prospectus_financial_packet.v1");
        packet.setReviewStatus("reviewed");
        packet.setCompany(new ProspectusCompanyIdentity(
                "Space Exploration Technologies Corp.",
                "SPCX",
                "United States",
                "USD",
                "aerospace-defense"));
        packet.setFiling(new ProspectusFilingMetadata(
                "S-1/A",
                "0001181412",
                "0001628280-26-040364",
                "2026-06-03"));
        packet.setSourceUrl("https://www.sec.gov/Archives/edgar/data/1181412/000162828026040364/spaceexplorationtechnologib.htm");
        packet.setSourceProvenance(provenance);
        packet.getFinancials().setIncomeStatement(new ArrayList<>(List.of(
                fact("revenue", "Revenue", "Year Ended December 31, 2025", 1_200_000_000.0, "millions", provenance),
                fact("prior_revenue", "Revenue", "Year Ended December 31, 2024", 900_000_000.0, "millions", provenance),
                fact("operating_income", "Operating income (loss)", "Year Ended December 31, 2025", 120_000_000.0, "millions", provenance),
                fact("research_and_development", "Research and development", "Year Ended December 31, 2025", 250_000_000.0, "millions", provenance))));
        packet.getFinancials().setBalanceSheet(new ArrayList<>(List.of(
                fact("cash_and_short_term_investments", "Cash and cash equivalents", "December 31, 2025", 500_000_000.0, "millions", provenance),
                fact("total_debt", "Total debt", "December 31, 2025", 300_000_000.0, "millions", provenance),
                fact("book_value_equity", "Total stockholders' equity", "December 31, 2025", 700_000_000.0, "millions", provenance))));
        packet.setOffering(new ProspectusOfferingFacts(
                135.0,
                "offering_price",
                null,
                400_000_000.0,
                "pro_forma_post_offering"));
        packet.setShareCounts(new ArrayList<>(List.of(shareCount("pro_forma_post_offering", 400_000_000.0))));
        return packet;
    }

    public static ProspectusFinancialPacket spaceXSegmentMixPacket() {
        ProspectusFinancialPacket packet = reviewedPacket();
        packet.setSegments(new ArrayList<>(List.of(
                segment("Connectivity", 11_387_000_000.0, 0.61, "telecom-services", "Telecom. Services", "medium"),
                segment("Space", 4_086_000_000.0, 0.22, "aerospace-defense", "Aerospace/Defense", "medium"),
                segment("AI", 3_201_000_000.0, 0.17, null, null, "low"))));
        return packet;
    }

    public static ProspectusFact fact(
            String canonicalField,
            String rowLabel,
            String columnLabel,
            double normalizedValue,
            String scale,
            SourceProvenance provenance) {
        ProspectusFact fact = new ProspectusFact();
        fact.setCanonicalField(canonicalField);
        fact.setSourceRowLabel(rowLabel);
        fact.setOriginalColumnLabel(columnLabel);
        fact.setTableTitle("Consolidated Statements");
        fact.setPeriodEnd(columnLabel.contains("2024") ? "2024-12-31" : "2025-12-31");
        fact.setUnit("USD");
        fact.setScale(scale);
        fact.setRawValue(String.valueOf(normalizedValue));
        fact.setNormalizedValue(normalizedValue);
        fact.setConfidence(0.95);
        fact.setSourceProvenance(provenance);
        return fact;
    }

    public static ProspectusShareCountFact shareCount(String basis, double normalizedValue) {
        ProspectusShareCountFact fact = new ProspectusShareCountFact();
        fact.setBasis(basis);
        fact.setSourceRowLabel(basis);
        fact.setOriginalColumnLabel("Pro forma as adjusted");
        fact.setNormalizedValue(normalizedValue);
        fact.setConfidence(0.9);
        return fact;
    }

    public static ProspectusSegmentFact segment(
            String name,
            double revenueAmount,
            double revenueWeight,
            String sectorKey,
            String mappedIndustry,
            String mappingConfidence) {
        ProspectusSegmentFact segment = new ProspectusSegmentFact();
        segment.setSegmentName(name);
        segment.setRevenueAmount(revenueAmount);
        segment.setRevenueWeight(revenueWeight);
        segment.setSectorKey(sectorKey);
        segment.setMappedIndustry(mappedIndustry);
        segment.setMappingConfidence(mappingConfidence);
        segment.setSourceRowLabel(name);
        segment.setTableTitle("Segment Revenue");
        segment.setPeriodEnd("2025-12-31");
        return segment;
    }
}
