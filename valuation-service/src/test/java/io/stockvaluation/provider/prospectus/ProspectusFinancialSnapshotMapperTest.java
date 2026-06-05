package io.stockvaluation.provider.prospectus;

import io.stockvaluation.provider.BalanceSheetSnapshot;
import io.stockvaluation.provider.IncomeStatementSnapshot;
import io.stockvaluation.provider.SourceProvenance;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ProspectusFinancialSnapshotMapperTest {

    @Test
    void mapsReviewedPacketIntoProviderNeutralSnapshots() {
        ProspectusMappedSnapshots mapped = new ProspectusFinancialSnapshotMapper()
                .map(ProspectusTestPackets.reviewedPacket());

        IncomeStatementSnapshot income = mapped.yearlyIncome().values().iterator().next();
        assertEquals(1_200_000_000.0, income.totalRevenue());
        assertEquals(120_000_000.0, income.operatingIncome());
        assertEquals(250_000_000.0, income.researchAndDevelopment());
        assertEquals(SourceProvenance.PRIMARY_FILING, income.sourceProvenance().getSourceClass());
        assertEquals("sec-edgar-prospectus", income.sourceProvenance().getProvider());

        BalanceSheetSnapshot balance = mapped.yearlyBalance().values().iterator().next();
        assertEquals(700_000_000.0, balance.bookValueEquity());
        assertEquals(300_000_000.0, balance.totalDebt());
        assertEquals(500_000_000.0, balance.cashAndShortTermInvestments());
        assertEquals(400_000_000.0, balance.sharesOutstanding());
    }

    @Test
    void keepsFirstFactWhenDiscussionTablesRepeatSamePeriod() {
        ProspectusFinancialPacket packet = ProspectusTestPackets.reviewedPacket();
        SourceProvenance provenance = packet.getSourceProvenance();
        packet.getFinancials().getIncomeStatement().add(ProspectusTestPackets.fact(
                "operating_income",
                "Income (loss) from operations",
                "Year Ended December 31, 2025",
                999_000_000.0,
                "millions",
                provenance));
        packet.getFinancials().getBalanceSheet().add(ProspectusTestPackets.fact(
                "total_debt",
                "Total debt",
                "December 31, 2025",
                999_000_000.0,
                "millions",
                provenance));

        ProspectusMappedSnapshots mapped = new ProspectusFinancialSnapshotMapper().map(packet);

        IncomeStatementSnapshot income = mapped.yearlyIncome().values().iterator().next();
        BalanceSheetSnapshot balance = mapped.yearlyBalance().values().iterator().next();
        assertEquals(120_000_000.0, income.operatingIncome());
        assertEquals(300_000_000.0, balance.totalDebt());
    }
}
