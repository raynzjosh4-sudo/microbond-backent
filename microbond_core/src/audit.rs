use pyo3::prelude::*;
use sha2::{Digest, Sha256};

pub fn compute_canonical_audit_hash(previous_hash: &str, event_json: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(previous_hash.as_bytes());
    hasher.update(b":");
    hasher.update(event_json.as_bytes());
    format!("{:x}", hasher.finalize())
}

#[pyfunction]
pub fn canonical_audit_hash(previous_hash: &str, event_json: &str) -> PyResult<String> {
    Ok(compute_canonical_audit_hash(previous_hash, event_json))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_audit_hash_deterministic() {
        let hash1 = compute_canonical_audit_hash("0000000000000000000000000000000000000000000000000000000000000000", r#"{"action":"TEST"}"#);
        let hash2 = compute_canonical_audit_hash("0000000000000000000000000000000000000000000000000000000000000000", r#"{"action":"TEST"}"#);
        assert_eq!(hash1, hash2);
        assert_eq!(hash1.len(), 64);
    }

    #[test]
    fn test_audit_hash_chain_sensitive() {
        let hash1 = compute_canonical_audit_hash("hash_a", r#"{"action":"TEST"}"#);
        let hash2 = compute_canonical_audit_hash("hash_b", r#"{"action":"TEST"}"#);
        assert_ne!(hash1, hash2);
    }
}
