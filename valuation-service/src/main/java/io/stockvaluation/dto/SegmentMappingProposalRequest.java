package io.stockvaluation.dto;

import java.util.List;

public record SegmentMappingProposalRequest(
        List<SegmentRow> segments,
        Double consolidatedRevenue) {

    public record SegmentRow(
            String name,
            Double revenueAmount,
            Double revenueWeight,
            List<String> components,
            String rowRole,
            String tableTitle,
            List<String> warnings) {
    }
}
