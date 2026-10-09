package com.microbond.app.models.groupmodel

import com.microbond.app.core.data_classes_and_enums.SavingsGroupType
import java.util.UUID

/**
 * One stored value of one metric for one group at one point in time.
 * A chart is simply a list of these for the same [metricId], ordered by [periodStart].
 *
 * Example: metricId = "total_accumulation", granularity = WEEK → 8 snapshots = 8 points.
 *
 * Snapshots are written when a cycle closes (or by a scheduled job) from the
 * transactions / memberships, so charts don't have to re-scan the whole ledger.
 */
data class GroupMetricSnapshot(
    val snapshotId: String = UUID.randomUUID().toString(),
    val groupId: String,
    val metricId: String,                           // Key from GroupMetricDefinition.id
    val granularity: MetricGranularity,
    val periodStart: Long,
    val periodEnd: Long,
    val value: Double,
    val segments: Map<String, Double> = emptyMap(), // For pie/donut metrics e.g. {"MTN": 72.0, "Airtel": 20.0}
    val calculatedAt: Long = System.currentTimeMillis()
)

/**
 * Catalogue entry describing a metric (static, shipped with the app / config).
 * Replaces the separate lists in StatisticsScreen.axisMetrics and sampleMetrics.kt.
 */
data class GroupMetricDefinition(
    val id: String,                                 // e.g. "total_accumulation"
    val label: String,                              // e.g. "Total accumulation"
    val description: String = "",
    val category: MetricCategoryType,
    val unit: MetricUnit,
    val preferredChart: MetricChartKind = MetricChartKind.LINE,
    val applicableGroupTypes: Set<SavingsGroupType> = SavingsGroupType.entries.toSet()
)

enum class MetricGranularity {
    DAY,
    WEEK,
    MONTH,
    YEAR
}

enum class MetricUnit {
    CURRENCY,       // Amount in group currency
    PERCENT,
    COUNT,          // Members, payouts, requests…
    DAYS,
    SCORE
}

enum class MetricCategoryType {
    SAVING,
    MEMBERS,
    PAYOUTS,
    PAYMENTS,
    FUNDRAISER,
    RISK,
    SOCIAL
}

enum class MetricChartKind {
    LINE,
    BAR,
    AREA,
    PIE,
    HEATMAP
}
