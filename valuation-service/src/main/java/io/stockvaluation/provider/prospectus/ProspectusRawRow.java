package io.stockvaluation.provider.prospectus;

import java.util.List;

public record ProspectusRawRow(
        String label,
        List<ProspectusRawCell> cells) {
}
