package io.stockvaluation.provider;

/**
 * Deterministic primary-filing financial provider for researched US valuations.
 *
 * <p>The valuation workflow asks this provider explicitly before falling back to
 * Yahoo-normalized financials. That keeps "primary source missing" as a checked
 * status instead of an inference from the current provider name.</p>
 */
public interface PrimaryFilingDataProvider extends FinancialSnapshotProvider {

    boolean hasPrimaryFinancials(String ticker);
}
