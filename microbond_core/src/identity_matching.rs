use pyo3::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NameSimilarityResult {
    pub is_similar: bool,
    pub similarity_percentage: f64,
    pub normalized_a: String,
    pub normalized_b: String,
}

fn normalize_and_sort_tokens(name: &str) -> String {
    let mut tokens: Vec<&str> = name
        .split_whitespace()
        .filter(|t| !t.is_empty())
        .collect();
    tokens.sort_unstable();
    tokens.join(" ")
}

fn levenshtein_distance(s1: &str, s2: &str) -> usize {
    let v1: Vec<char> = s1.chars().collect();
    let v2: Vec<char> = s2.chars().collect();

    let len1 = v1.len();
    let len2 = v2.len();

    if len1 == 0 {
        return len2;
    }
    if len2 == 0 {
        return len1;
    }

    let mut prev_row: Vec<usize> = (0..=len2).collect();
    let mut curr_row = vec![0; len2 + 1];

    for i in 0..len1 {
        curr_row[0] = i + 1;
        for j in 0..len2 {
            let cost = if v1[i] == v2[j] { 0 } else { 1 };
            curr_row[j + 1] = std::cmp::min(
                std::cmp::min(curr_row[j] + 1, prev_row[j + 1] + 1),
                prev_row[j] + cost,
            );
        }
        prev_row.copy_from_slice(&curr_row);
    }

    prev_row[len2]
}

pub fn is_name_similar_pure(name_a: &str, name_b: &str, threshold: f64) -> NameSimilarityResult {
    if name_a.trim().is_empty() || name_b.trim().is_empty() {
        return NameSimilarityResult {
            is_similar: false,
            similarity_percentage: 0.0,
            normalized_a: "".to_string(),
            normalized_b: "".to_string(),
        };
    }

    let clean_a = normalize_and_sort_tokens(&name_a.to_lowercase());
    let clean_b = normalize_and_sort_tokens(&name_b.to_lowercase());

    if clean_a == clean_b {
        return NameSimilarityResult {
            is_similar: true,
            similarity_percentage: 100.0,
            normalized_a: clean_a,
            normalized_b: clean_b,
        };
    }

    let dist = levenshtein_distance(&clean_a, &clean_b);
    let max_len = std::cmp::max(clean_a.chars().count(), clean_b.chars().count());

    let similarity_percentage = if max_len == 0 {
        100.0
    } else {
        ((max_len - dist) as f64 / max_len as f64) * 100.0
    };

    let is_similar = similarity_percentage >= threshold;

    NameSimilarityResult {
        is_similar,
        similarity_percentage,
        normalized_a: clean_a,
        normalized_b: clean_b,
    }
}

#[pyfunction]
#[pyo3(signature = (name_a, name_b, threshold=75.0))]
pub fn is_name_similar(name_a: &str, name_b: &str, threshold: f64) -> PyResult<String> {
    let res = is_name_similar_pure(name_a, name_b, threshold);
    serde_json::to_string(&res).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_name_similarity_token_order() {
        // "Mugisha John" vs "John Mugisha" should be 100% after token sorting
        let res = is_name_similar_pure("Mugisha John", "John Mugisha", 75.0);
        assert!(res.is_similar);
        assert_eq!(res.similarity_percentage, 100.0);
    }

    #[test]
    fn test_name_similarity_minor_typo() {
        // "Kato Emmanuel" vs "Kato Emanuel"
        let res = is_name_similar_pure("Kato Emmanuel", "Kato Emanuel", 75.0);
        assert!(res.is_similar);
        assert!(res.similarity_percentage > 85.0);
    }
}
