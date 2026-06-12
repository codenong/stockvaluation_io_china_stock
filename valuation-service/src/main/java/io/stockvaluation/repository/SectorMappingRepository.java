package io.stockvaluation.repository;

import io.stockvaluation.domain.SectorMapping;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface SectorMappingRepository extends JpaRepository<SectorMapping, Long> {

    @Query(value = "Select * from sector_mapping where yahoo_industry_key =:industryName", nativeQuery = true)
    public SectorMapping findByIndustryName(String industryName);

    @Query(value = """
            SELECT DISTINCT sm.*
            FROM sector_mapping sm
            WHERE sm.yahoo_industry_key IS NOT NULL
              AND sm.industry_as_per_excel IS NOT NULL
              AND (
                    EXISTS (
                        SELECT 1
                        FROM industry_averages_us us
                        WHERE us.industry_name = sm.industry_as_per_excel
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM industry_averages_global global_avg
                        WHERE global_avg.industry_name = sm.industry_as_per_excel
                    )
              )
            """, nativeQuery = true)
    List<SectorMapping> findUsableForSegmentValuation();
}
