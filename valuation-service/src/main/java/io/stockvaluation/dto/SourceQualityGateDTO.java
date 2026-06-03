package io.stockvaluation.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.ArrayList;
import java.util.List;

@NoArgsConstructor
@AllArgsConstructor
@Getter
@Setter
public class SourceQualityGateDTO {

    private String status;
    private String reason;
    private boolean primarySourceExpected;
    private boolean fallbackSourceAvailable;
    private boolean crossCheckRequired;
    private List<String> allowedActions = new ArrayList<>();
}
