package io.stockvaluation.provider.prospectus;

import java.util.List;

public record ProspectusRawTable(
        String title,
        String currency,
        String scale,
        List<String> columns,
        List<ProspectusRawRow> rows,
        String sourceAnchor) {
}
