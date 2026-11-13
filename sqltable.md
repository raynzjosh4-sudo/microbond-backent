## Table `user`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `firebase_uid` | `varchar` |  Nullable |
| `phone_number` | `varchar` |  |
| `full_name` | `varchar` |  Nullable |
| `avatar_color` | `varchar` |  Nullable |
| `profile_picture_url` | `varchar` |  Nullable |
| `about_status` | `varchar` |  |
| `default_currency` | `varchar` |  |
| `kyc_status` | `varchar` |  |
| `kyc_tier` | `int4` |  |
| `trust_score` | `int4` |  |
| `is_verified` | `bool` |  |
| `is_phone_verified` | `bool` |  |
| `is_profile_complete` | `bool` |  |
| `hashed_pin` | `varchar` |  Nullable |
| `fcm_token` | `varchar` |  Nullable |
| `is_online` | `bool` |  |
| `last_seen_at` | `int8` |  Nullable |
| `referral_code` | `varchar` |  Nullable |
| `referred_by_code` | `varchar` |  Nullable |
| `total_referrals` | `int4` |  |
| `total_earned` | `float8` |  |
| `guardian_id` | `uuid` |  Nullable |
| `is_dependent_account` | `bool` |  |
| `daily_withdrawal_limit` | `float8` |  |
| `created_at` | `timestamptz` |  |
| `primary_device_id` | `varchar` |  Nullable |
| `security_cooldown_until` | `int8` |  Nullable |
| `profile_photo_visibility` | `varchar` |  |
| `about_visibility` | `varchar` |  |
| `group_add_permission` | `varchar` |  |

## Table `otprecord`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `phone_number` | `varchar` |  |
| `is_used` | `bool` |  |
| `created_at` | `timestamptz` |  |
| `expires_at` | `timestamptz` |  |
| `code_hash` | `text` |  Nullable |

## Table `group`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  Unique |
| `name` | `varchar` |  |
| `description` | `varchar` |  |
| `group_image_url` | `varchar` |  |
| `avatar_color` | `varchar` |  |
| `type` | `varchar` |  |
| `payment_mode` | `varchar` |  |
| `savings_term` | `varchar` |  |
| `visibility` | `varchar` |  |
| `status` | `varchar` |  |
| `currency` | `varchar` |  |
| `total_balance` | `int8` |  Nullable |
| `member_count` | `int4` |  |
| `max_members` | `int4` |  Nullable |
| `created_by_user_id` | `uuid` |  |
| `invite_code` | `varchar` |  Nullable |
| `shared_media_count` | `int4` |  |
| `shared_ledger_entry_count` | `int4` |  |
| `created_at` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |
| `start_date` | `int8` |  Nullable |

## Table `kycprofile`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `user_id` | `uuid` |  |
| `current_tier` | `varchar` |  |
| `overall_status` | `varchar` |  |
| `rejection_reason` | `varchar` |  Nullable |
| `sim_msisdn` | `varchar` |  Nullable |
| `sim_telecom_provider` | `varchar` |  Nullable |
| `sim_registered_name` | `varchar` |  Nullable |
| `is_mobile_money_active` | `bool` |  |
| `is_sim_name_matched` | `bool` |  |
| `sim_verified_at` | `int8` |  Nullable |
| `updated_at` | `timestamptz` |  |
| `first_name` | `varchar` |  Nullable |
| `last_name` | `varchar` |  Nullable |
| `nin` | `varchar` |  Nullable |
| `dob` | `varchar` |  Nullable |
| `document_id` | `varchar` |  Nullable |
| `middle_name` | `varchar` |  Nullable |
| `gender` | `varchar` |  Nullable |
| `last_known_sim_registration_timestamp` | `int8` |  Nullable |
| `sim_swap_detected` | `bool` |  |
| `last_carrier_subscriber_id` | `varchar` |  Nullable |
| `photo_storage_path` | `text` |  Nullable |
| `nin_last4` | `text` |  Nullable |
| `document_id_last4` | `text` |  Nullable |

## Table `kycdocument`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `user_id` | `uuid` |  |
| `document_type` | `varchar` |  |
| `document_number` | `varchar` |  |
| `front_image_path` | `varchar` |  |
| `back_image_path` | `varchar` |  Nullable |
| `selfie_image_path` | `varchar` |  Nullable |
| `extracted_full_name` | `varchar` |  Nullable |
| `date_of_birth` | `varchar` |  Nullable |
| `status` | `varchar` |  |
| `rejection_reason` | `varchar` |  Nullable |
| `submitted_at` | `int4` |  |
| `verified_at` | `int4` |  Nullable |
| `expiry_date` | `int4` |  Nullable |

## Table `groupmembership`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `membership_id` | `varchar` |  |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `role` | `varchar` |  |
| `title` | `varchar` |  Nullable |
| `status` | `varchar` |  |
| `group_trust_score` | `int4` |  Nullable |
| `total_contributed` | `int4` |  |
| `is_favorite` | `bool` |  |
| `unread_count` | `int4` |  |
| `invited_by_user_id` | `uuid` |  Nullable |
| `joined_at` | `int8` |  Nullable |
| `left_at` | `int8` |  Nullable |
| `auto_pay_my_turn` | `bool` |  |
| `proxy_contributor_id` | `uuid` |  Nullable |
| `payout_destination_id` | `varchar` |  Nullable |
| `payment_method_id` | `varchar` |  Nullable |
| `mute_notifications` | `bool` |  |
| `show_previews` | `bool` |  |
| `include_chat_in_export` | `bool` |  |
| `custom_notification_tone` | `varchar` |  Nullable |
| `is_chat_locked` | `bool` |  |
| `payout_position` | `int4` |  Nullable |
| `is_signer` | `bool` |  |
| `auto_approve_small_requests` | `bool` |  |
| `auto_approve_max_amount` | `float8` |  Nullable |
| `sms_reminders_opted_in` | `bool` |  |
| `sms_reminder_hours_before` | `int4` |  |
| `sms_fee_acknowledged` | `bool` |  |
| `pending_sms_fee_ugx` | `int4` |  |
| `email_reminders_opted_in` | `bool` |  |
| `email_reminder_hours_before` | `int4` |  |
| `credit_balance_ugx` | `int8` |  |

## Table `memberobligation`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `due_date` | `int8` |  Nullable |
| `status` | `varchar` |  |
| `created_at` | `int8` |  Nullable |
| `cycle_number` | `int4` |  |
| `amount_due` | `int8` |  Nullable |
| `amount_paid` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |
| `last_reminder_tier` | `int4` |  Nullable |
| `cycle_id` | `uuid` |  Nullable |
| `collection_id` | `uuid` |  Nullable |

## Table `invite`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `inviter_phone` | `varchar` |  |
| `invitee_phone` | `varchar` |  |
| `status` | `varchar` |  |
| `group_id` | `int4` |  Nullable |
| `created_at` | `timestamptz` |  |
| `inviter_user_id` | `uuid` |  Nullable |
| `invitee_user_id` | `uuid` |  Nullable |
| `invite_token_hash` | `text` |  Nullable |
| `expires_at` | `timestamptz` |  Nullable |
| `max_uses` | `int4` |  |
| `uses_count` | `int4` |  |
| `accepted_at` | `timestamptz` |  Nullable |
| `declined_at` | `timestamptz` |  Nullable |
| `revoked_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  |
| `group_public_id` | `varchar` |  Nullable |

## Table `rotatinggroupdetails`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `contribution_amount` | `float8` |  Nullable |
| `payouts_per_cycle` | `int4` |  |
| `number_of_cycles` | `int4` |  Nullable |
| `group_start_time` | `int8` |  Nullable |
| `payout_order_strategy` | `varchar` |  |
| `is_payout_order_locked` | `bool` |  |
| `total_expected_pool_per_cycle` | `float8` |  Nullable |
| `minimum_kyc_tier` | `int4` |  |
| `require_guarantor` | `bool` |  |
| `guarantor_default_action` | `varchar` |  |
| `allow_partial_payments` | `bool` |  |
| `allow_advance_deposits` | `bool` |  |
| `current_cycle` | `int4` |  |
| `created_at` | `int8` |  Nullable |
| `collection_frequency_days` | `int4` |  |
| `collection_time` | `varchar` |  Nullable |
| `auto_disburse_when_full` | `bool` |  |
| `multi_sig_payout_approval` | `bool` |  |
| `allow_turn_swaps` | `bool` |  |
| `turn_swap_approval_mode` | `varchar` |  |
| `early_turn_security_hold_percentage` | `float8` |  |
| `require_guarantors_for_early_turns_only` | `bool` |  |
| `auto_renew_cycle` | `bool` |  |
| `reverse_payout_order_on_renew` | `bool` |  |
| `reminder_lead_time_hours` | `int4` |  |
| `enable_auto_debit_prompt` | `bool` |  |
| `saving_days_per_cycle` | `int4` |  Nullable |
| `current_saving_day` | `int4` |  |
| `minimum_partial_payment_amount` | `float8` |  Nullable |
| `currency_code` | `varchar` |  |
| `timezone_name` | `text` |  |
| `collection_start_time` | `time` |  |
| `collection_end_time` | `time` |  |
| `cycle_length_days` | `int4` |  |
| `recipients_per_cycle` | `int4` |  |
| `reserve_percentage` | `numeric` |  |
| `reserve_purpose` | `text` |  Nullable |
| `payout_calculation_mode` | `text` |  |
| `payout_requires_full_collection` | `bool` |  |
| `late_payment_grace_minutes` | `int4` |  |
| `locked_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  |

## Table `alembic_version`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `version_num` | `varchar` | Primary |

## Table `groupchatmessage`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `sender_id` | `varchar` |  |
| `message_type` | `varchar` |  |
| `message_text` | `varchar` |  Nullable |
| `media_url` | `varchar` |  Nullable |
| `reply_to_message_id` | `uuid` |  Nullable |
| `is_deleted` | `bool` |  |
| `created_at` | `int8` |  Nullable |
| `client_message_id` | `varchar` |  Nullable |
| `media_type` | `varchar` |  Nullable |
| `media_mime_type` | `varchar` |  Nullable |
| `media_size_bytes` | `int4` |  Nullable |
| `media_duration_seconds` | `int4` |  Nullable |
| `status` | `varchar` |  |
| `updated_at` | `int8` |  Nullable |
| `attachments` | `json` |  Nullable |
| `media_width` | `int4` |  Nullable |
| `media_height` | `int4` |  Nullable |
| `aspect_ratio` | `float8` |  Nullable |
| `sender_user_id` | `uuid` |  Nullable |

## Table `groupwallet`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `pooled_funds` | `int8` |  Nullable |
| `reserve_funds` | `int8` |  Nullable |
| `total_lifetime_payouts` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |
| `prepaid_funds` | `int8` |  |

## Table `grouppayout`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `cycle_number` | `int4` |  |
| `amount_expected` | `int8` |  Nullable |
| `amount_received` | `int8` |  Nullable |
| `status` | `varchar` |  |
| `payout_date` | `int8` |  Nullable |
| `created_at` | `int8` |  Nullable |
| `hold_reason` | `varchar` |  Nullable |
| `rotating_payout_id` | `uuid` |  Nullable |

## Table `guarantorpledge`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `guarantor_user_id` | `uuid` |  |
| `borrower_user_id` | `uuid` |  |
| `maximum_liability_amount` | `int8` |  Nullable |
| `status` | `varchar` |  |
| `created_at` | `int8` |  Nullable |
| `pledge_token_hash` | `text` |  Nullable |

## Table `grouppenalty`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `obligation_id` | `int4` |  Nullable |
| `penalty_amount` | `int8` |  Nullable |
| `reason` | `varchar` |  |
| `is_paid` | `bool` |  |
| `created_at` | `int8` |  Nullable |

## Table `groupcommunicationsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `broadcast_individual_deposit_receipts` | `bool` |  |
| `announce_payout_updates` | `bool` |  |
| `show_transfer_receipts` | `bool` |  |
| `announce_admin_transactions` | `bool` |  |
| `send_daily_group_summaries` | `bool` |  |
| `daily_summary_time` | `varchar` |  |
| `post_weekly_financial_reports` | `bool` |  |
| `weekly_report_day` | `varchar` |  |
| `weekly_report_time` | `varchar` |  |
| `send_deposit_due_prompts` | `bool` |  |
| `share_financial_snapshots` | `bool` |  |
| `announce_system_events` | `bool` |  |
| `post_security_rule_updates` | `bool` |  |
| `post_group_approval_polls` | `bool` |  |
| `notify_important_rule_changes` | `bool` |  |
| `chat_history_cleanup_days` | `int4` |  |
| `preserve_financial_records` | `bool` |  |
| `updated_at` | `int8` |  Nullable |
| `data_retention_days` | `int4` |  |
| `enable_automated_audit_dispatch` | `bool` |  |
| `audit_report_recipient_email` | `varchar` |  Nullable |
| `dispatch_monthly_compliance_statement` | `bool` |  |
| `export_file_format` | `varchar` |  |
| `send_loan_due_prompts` | `bool` |  |
| `broadcast_individual_loan_receipts` | `bool` |  |
| `announce_loan_disbursement_updates` | `bool` |  |
| `post_loan_approval_polls` | `bool` |  |
| `send_dues_due_prompts` | `bool` |  |
| `broadcast_individual_dues_receipts` | `bool` |  |
| `announce_dues_adjustment_updates` | `bool` |  |

## Table `groupfinancialsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `enforce_payout_holds` | `bool` |  |
| `allow_substitute_members` | `bool` |  |
| `enable_late_fees` | `bool` |  |
| `late_fee_amount` | `float8` |  |
| `late_fee_frequency` | `varchar` |  |
| `enable_grace_period` | `bool` |  |
| `arrears_policy` | `varchar` |  |
| `max_payout_active` | `bool` |  |
| `max_payout_limit` | `varchar` |  |
| `reserve_fund_percentage` | `float8` |  |
| `enable_escrow` | `bool` |  |
| `escrow_release_condition` | `varchar` |  |
| `enable_timelock` | `bool` |  |
| `updated_at` | `int8` |  Nullable |
| `grace_period_hours` | `int4` |  |
| `max_pending_payouts` | `int4` |  |
| `timelock_duration_hours` | `int4` |  |
| `liquidity_buffer_percentage` | `float8` |  |
| `enable_late_fee_escalation` | `bool` |  |
| `contribution_reminder_days_before` | `int4` |  |
| `auto_debit_consent_required` | `bool` |  |
| `emergency_contact_name` | `varchar` |  Nullable |
| `emergency_contact_phone` | `varchar` |  Nullable |
| `enable_sms_call_reminders` | `bool` |  |

## Table `groupgovernancesettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `is_audit_active` | `bool` |  |
| `require_multi_signature` | `bool` |  |
| `multi_sig_required_approvals` | `int4` |  |
| `approval_strategy` | `varchar` |  |
| `quorum_percentage` | `varchar` |  |
| `require_guarantors` | `bool` |  |
| `guarantor_count` | `int4` |  |
| `minimum_trust_score` | `int4` |  Nullable |
| `members_can_edit_settings` | `bool` |  |
| `members_can_send_messages` | `bool` |  |
| `members_can_invite_via_link` | `bool` |  |
| `members_can_manage_payout_roster` | `bool` |  |
| `requires_admin_approval` | `bool` |  |
| `updated_at` | `int8` |  Nullable |
| `group_charter_url` | `varchar` |  Nullable |
| `enable_quorum_decay` | `bool` |  |
| `quorum_decay_hours` | `int4` |  |
| `quorum_decay_minimum_approvals` | `int4` |  |
| `minimum_kyc_tier` | `int4` |  |

## Table `groupvisibilitysettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `hide_total_group_balance` | `bool` |  |
| `hide_member_contact_info` | `bool` |  |
| `invite_only_discoverability` | `bool` |  |
| `vis_manage_payout_order` | `bool` |  |
| `vis_late_fee_penalties` | `bool` |  |
| `vis_grace_period_window` | `bool` |  |
| `vis_enforce_payout_holds` | `bool` |  |
| `vis_substitute_member_allowance` | `bool` |  |
| `vis_multi_signature_roster` | `bool` |  |
| `vis_active_audit_status` | `bool` |  |
| `vis_approval_quorum` | `bool` |  |
| `vis_pending_payout_queue` | `bool` |  |
| `vis_require_multi_signature` | `bool` |  |
| `vis_time_lock_disbursals` | `bool` |  |
| `vis_guarantor_required` | `bool` |  |
| `vis_contribution_reminder_schedule` | `bool` |  |
| `vis_liquidity_buffer_coverage` | `bool` |  |
| `vis_late_fee_escalation` | `bool` |  |
| `vis_download_official_statement` | `bool` |  |
| `vis_chat_history_cleanup` | `bool` |  |
| `vis_broadcast_individual_deposit_receipts` | `bool` |  |
| `vis_announce_payout_updates` | `bool` |  |
| `vis_show_transfer_receipts` | `bool` |  |
| `vis_announce_admin_transactions` | `bool` |  |
| `vis_send_daily_group_summaries` | `bool` |  |
| `vis_post_weekly_financial_reports` | `bool` |  |
| `vis_send_deposit_due_prompts` | `bool` |  |
| `vis_daily_summary_time` | `bool` |  |
| `vis_weekly_report_day` | `bool` |  |
| `vis_share_financial_snapshots` | `bool` |  |
| `vis_announce_system_events` | `bool` |  |
| `vis_post_security_rule_updates` | `bool` |  |
| `vis_post_group_approval_polls` | `bool` |  |
| `vis_notify_important_rule_changes` | `bool` |  |
| `updated_at` | `int8` |  Nullable |
| `vis_report_expected_revenue` | `bool` |  |
| `vis_report_actual_collection` | `bool` |  |
| `vis_report_deficit` | `bool` |  |
| `vis_report_reserve_fund` | `bool` |  |
| `vis_report_escrow_holds` | `bool` |  |
| `vis_dues_schedule` | `bool` |  |
| `vis_allow_installments` | `bool` |  |
| `vis_arrears_policy` | `bool` |  |
| `vis_fee_exemptions` | `bool` |  |
| `vis_pending_dues_adjustments` | `bool` |  |
| `vis_broadcast_individual_dues_receipts` | `bool` |  |
| `vis_announce_dues_adjustment_updates` | `bool` |  |
| `vis_send_dues_due_prompts` | `bool` |  |
| `vis_interest_rates` | `bool` |  |
| `vis_loan_guarantor_rules` | `bool` |  |
| `vis_max_borrowing_limit` | `bool` |  |
| `vis_early_repayment_discount` | `bool` |  |
| `vis_new_share_issuance` | `bool` |  |
| `vis_default_asset_seizure` | `bool` |  |
| `vis_pending_loans` | `bool` |  |
| `vis_auto_debit_consent` | `bool` |  |
| `vis_emergency_contact` | `bool` |  |
| `vis_sms_call_reminders` | `bool` |  |
| `vis_send_loan_due_prompts` | `bool` |  |
| `vis_broadcast_individual_loan_receipts` | `bool` |  |
| `vis_announce_loan_disbursement_updates` | `bool` |  |
| `vis_post_loan_approval_polls` | `bool` |  |
| `deposit_widget_visibility` | `varchar` |  |
| `vis_member_total_savings` | `bool` |  |

## Table `userpayoutdestination`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `varchar` | Primary |
| `user_id` | `uuid` |  |
| `provider_name` | `varchar` |  |
| `account_number` | `varchar` |  |
| `account_name` | `varchar` |  Nullable |
| `is_default` | `bool` |  |
| `created_at` | `int8` |  Nullable |
| `account_type` | `varchar` |  |
| `is_verified` | `bool` |  |
| `verified_name` | `varchar` |  Nullable |
| `verification_type` | `varchar` |  Nullable |

## Table `turnswaprequest`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `swap_request_id` | `varchar` |  |
| `group_id` | `varchar` |  |
| `requester_user_id` | `uuid` |  |
| `target_user_id` | `uuid` |  |
| `requester_cycle_number` | `int4` |  |
| `target_cycle_number` | `int4` |  |
| `status` | `varchar` |  |
| `created_at` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |

## Table `userpaymentmethod`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `varchar` | Primary |
| `user_id` | `uuid` |  |
| `provider_name` | `varchar` |  |
| `account_number` | `varchar` |  |
| `account_name` | `varchar` |  Nullable |
| `is_default` | `bool` |  |
| `created_at` | `int8` |  Nullable |
| `account_type` | `varchar` |  |
| `is_verified` | `bool` |  |
| `verified_name` | `varchar` |  Nullable |
| `verification_type` | `varchar` |  Nullable |

## Table `groupreport`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `report_id` | `varchar` |  |
| `group_id` | `varchar` |  |
| `reporter_user_id` | `uuid` |  |
| `reason` | `varchar` |  |
| `description` | `varchar` |  Nullable |
| `status` | `varchar` |  |
| `created_at` | `int8` |  Nullable |
| `reported_user_id` | `uuid` |  Nullable |

## Table `groupchatreadreceipt`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `message_id` | `uuid` | Primary |
| `user_id` | `varchar` | Primary |
| `read_at` | `int8` |  Nullable |
| `user_uuid` | `uuid` |  Nullable |

## Table `grouppoll`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `creator_id` | `uuid` |  |
| `question` | `varchar` |  |
| `options` | `varchar` |  |
| `poll_type` | `varchar` |  |
| `status` | `varchar` |  |
| `expires_at` | `int8` |  Nullable |
| `created_at` | `int8` |  Nullable |

## Table `groupauction`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `auction_id` | `varchar` |  Unique |
| `group_id` | `varchar` |  |
| `cycle_number` | `int4` |  |
| `start_time` | `int8` |  Nullable |
| `end_time` | `int8` |  Nullable |
| `status` | `varchar` |  |
| `winning_bid_id` | `int4` |  Nullable |
| `winning_user_id` | `varchar` |  Nullable |
| `created_at` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |

## Table `auctionbid`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `auction_id` | `varchar` |  |
| `user_id` | `varchar` |  |
| `bid_amount` | `float8` |  |
| `status` | `varchar` |  |
| `created_at` | `int8` |  Nullable |

## Table `grouppollvote`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `poll_id` | `uuid` | Primary |
| `user_id` | `uuid` | Primary |
| `selected_option` | `varchar` |  |
| `created_at` | `int8` |  Nullable |

## Table `grouphealth`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `health_grade` | `varchar` |  |
| `risk_level` | `varchar` |  |
| `on_time_repayment_rate_pct` | `float8` |  |
| `active_default_rate_pct` | `float8` |  |
| `total_defaulted_amount` | `float8` |  |
| `members_in_arrears_count` | `int4` |  |
| `liquidity_ratio` | `float8` |  |
| `reserve_fund_balance` | `float8` |  |
| `average_member_trust_score` | `float8` |  |
| `consecutive_successful_cycles` | `int4` |  |
| `dispute_rate_pct` | `float8` |  |
| `last_recalculated_at` | `int8` |  Nullable |

## Table `usersecurityemail`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `user_id` | `uuid` |  |
| `email` | `varchar` |  |
| `is_verified` | `bool` |  |
| `verification_expires_at` | `int8` |  Nullable |
| `created_at` | `timestamptz` |  |
| `verified_at` | `timestamptz` |  Nullable |
| `verification_token_hash` | `text` |  Nullable |

## Table `targetsavingsgroupdetails`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `target_amount` | `int8` |  Nullable |
| `target_date` | `int8` |  Nullable |
| `contribution_amount` | `int8` |  Nullable |
| `collection_frequency_days` | `int4` |  |
| `collection_time` | `int8` |  Nullable |
| `payout_destination_type` | `varchar` |  |
| `nominated_account_id` | `varchar` |  Nullable |
| `require_consensus_at_end` | `bool` |  |
| `allow_early_payout_by_vote` | `bool` |  |
| `vote_approval_percentage` | `int4` |  |
| `enable_late_fees` | `bool` |  |
| `late_fee_amount` | `int8` |  Nullable |
| `grace_period_hours` | `int4` |  |
| `missed_payment_action` | `varchar` |  |
| `minimum_kyc_tier` | `int4` |  |
| `hide_leaderboard` | `bool` |  |
| `is_locked` | `bool` |  |
| `is_ended` | `bool` |  |
| `is_paid_out` | `bool` |  |
| `total_saved_amount` | `int8` |  Nullable |
| `created_at` | `int8` |  Nullable |
| `allow_target_amount` | `bool` |  |
| `allow_target_date` | `bool` |  |
| `allow_contribution_schedule` | `bool` |  |
| `allow_collection_frequency` | `bool` |  |
| `allow_multi_payout` | `bool` |  |

## Table `fundraisercampaignconfig`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `target_amount` | `int8` |  Nullable |
| `campaign_deadline` | `int8` |  Nullable |
| `payout_destination_type` | `varchar` |  |
| `nominated_account_id` | `varchar` |  Nullable |
| `payout_trigger_mode` | `varchar` |  |
| `require_multi_signoff` | `bool` |  |
| `signoff_count_required` | `int4` |  |
| `created_at` | `int8` |  Nullable |

## Table `fundraiserlivestats`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `allow_overfunding` | `bool` |  |
| `stop_on_target_reached` | `bool` |  |
| `minimum_donation_amount` | `int8` |  Nullable |
| `is_active` | `bool` |  |
| `is_paid_out` | `bool` |  |
| `total_raised` | `int8` |  Nullable |
| `donor_count` | `int4` |  |
| `updated_at` | `int8` |  Nullable |

## Table `sharedwalletconfig`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `replenishment_mode` | `varchar` |  |
| `member_quota_amount` | `int8` |  Nullable |
| `collection_frequency_days` | `int4` |  |
| `spending_signoff_policy` | `varchar` |  |
| `exit_payout_rule` | `varchar` |  |
| `track_individual_contributions` | `bool` |  |
| `minimum_kyc_tier` | `int4` |  |
| `created_at` | `int8` |  Nullable |

## Table `sharedwalletoperationalsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `minimum_balance_floor` | `int8` |  Nullable |
| `target_budget_limit` | `int8` |  Nullable |
| `auto_approve_threshold` | `int8` |  Nullable |
| `approval_timeout_hours` | `int4` |  |
| `timelock_duration_hours` | `int4` |  |
| `daily_spending_cap` | `int8` |  Nullable |
| `per_transaction_cap` | `int8` |  Nullable |
| `allowed_disbursement_types` | `varchar` |  |
| `current_balance` | `int8` |  Nullable |
| `total_deposited` | `int8` |  Nullable |
| `total_spent` | `int8` |  Nullable |
| `is_active` | `bool` |  |
| `updated_at` | `int8` |  Nullable |

## Table `welfarefundconfig`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `contribution_amount` | `int8` |  Nullable |
| `collection_frequency_days` | `int4` |  |
| `waiting_period_days` | `int4` |  |
| `max_claim_amount_per_incident` | `int8` |  Nullable |
| `annual_claim_limit_per_member` | `int8` |  Nullable |
| `payout_destination_type` | `varchar` |  |
| `requires_documentary_evidence` | `bool` |  |
| `claim_approval_policy` | `varchar` |  |
| `created_at` | `int8` |  Nullable |

## Table `welfarefundoperationalsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `minimum_reserve_balance` | `int8` |  Nullable |
| `approval_timeout_hours` | `int4` |  |
| `missed_payment_action` | `varchar` |  |
| `enable_late_fees` | `bool` |  |
| `allow_annual_dividend_split` | `bool` |  |
| `current_balance` | `int8` |  Nullable |
| `total_collected` | `int8` |  Nullable |
| `total_paid_out` | `int8` |  Nullable |
| `is_active` | `bool` |  |
| `updated_at` | `int8` |  Nullable |

## Table `eventcommitteeconfig`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `event_target_budget` | `int8` |  Nullable |
| `event_date` | `int8` |  Nullable |
| `collection_deadline` | `int8` |  Nullable |
| `payout_destination_type` | `varchar` |  |
| `spending_signoff_policy` | `varchar` |  |
| `excess_funds_action` | `varchar` |  |
| `require_invoice_upload` | `bool` |  |
| `created_at` | `int8` |  Nullable |

## Table `eventcommitteeoperationalsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `allow_overfunding` | `bool` |  |
| `track_pledges` | `bool` |  |
| `minimum_contribution_amount` | `int8` |  Nullable |
| `member_quota_amount` | `int8` |  Nullable |
| `allow_guest_deposits` | `bool` |  |
| `allow_partial_disbursements` | `bool` |  |
| `signoff_trustee_user_ids` | `varchar` |  |
| `current_balance` | `int8` |  Nullable |
| `total_pledged` | `int8` |  Nullable |
| `total_disbursed` | `int8` |  Nullable |
| `is_active` | `bool` |  |
| `updated_at` | `int8` |  Nullable |

## Table `investmentclubconfig`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `share_unit_price` | `int8` |  Nullable |
| `equity_calculation_mode` | `varchar` |  |
| `voting_power_logic` | `varchar` |  |
| `payout_destination_type` | `varchar` |  |
| `dividend_distribution_rule` | `varchar` |  |
| `lock_in_period_days` | `int4` |  |
| `liquidation_action` | `varchar` |  |
| `created_at` | `int8` |  Nullable |

## Table `investmentcluboperationalsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `minimum_purchase_quota` | `int4` |  |
| `proposal_approval_threshold_pct` | `int4` |  |
| `admin_management_fee_pct` | `int4` |  |
| `allow_internal_share_transfers` | `bool` |  |
| `enable_late_fees` | `bool` |  |
| `current_balance` | `int8` |  Nullable |
| `total_invested_capital` | `int8` |  Nullable |
| `total_shares_issued` | `int8` |  Nullable |
| `total_dividends_distributed` | `int8` |  Nullable |
| `is_active` | `bool` |  |
| `updated_at` | `int8` |  Nullable |
| `interest_rate_mode` | `varchar` |  |
| `fixed_interest_rate_pct` | `float8` |  |
| `require_loan_guarantors` | `bool` |  |
| `min_loan_guarantors` | `int4` |  |
| `max_borrowing_limit` | `int8` |  Nullable |
| `early_repayment_discount_pct` | `float8` |  |
| `new_share_issuance_mode` | `varchar` |  |
| `default_recovery_action` | `varchar` |  |
| `contribution_reminder_days_before` | `int4` |  |
| `auto_debit_consent_required` | `bool` |  |
| `emergency_contact_name` | `varchar` |  Nullable |
| `emergency_contact_phone` | `varchar` |  Nullable |
| `liquidity_buffer_coverage_pct` | `int4` |  |
| `enable_late_fee_escalation` | `bool` |  |
| `enable_sms_call_reminders` | `bool` |  |
| `active_loans_count` | `int4` |  |
| `total_loans_disbursed` | `int8` |  Nullable |

## Table `investmentclubmembershare`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `shares_owned` | `int4` |  |
| `total_invested` | `int8` |  Nullable |
| `last_dividend_received` | `int8` |  Nullable |
| `created_at` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |

## Table `associationduesconfig`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `dues_amount` | `int8` |  Nullable |
| `billing_cycle_days` | `int4` |  |
| `billing_start_date` | `int8` |  Nullable |
| `treasury_account_id` | `varchar` |  |
| `enable_prorated_dues` | `bool` |  |
| `created_at` | `int8` |  Nullable |

## Table `associationduesoperationalsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `auto_sweep_trigger` | `varchar` |  |
| `allow_advance_payments` | `bool` |  |
| `grace_period_days` | `int4` |  |
| `late_fee_amount` | `int8` |  Nullable |
| `arrears_action` | `varchar` |  |
| `max_missed_cycles_allowed` | `int4` |  |
| `show_defaulters_publicly` | `bool` |  |
| `treasury_ledger_visibility` | `varchar` |  |
| `current_balance` | `int8` |  Nullable |
| `total_collected` | `int8` |  Nullable |
| `total_swept_to_treasury` | `int8` |  Nullable |
| `active_defaulters_count` | `int4` |  |
| `is_active` | `bool` |  |
| `updated_at` | `int8` |  Nullable |
| `allow_installments` | `bool` |  |
| `send_arrears_reminders` | `bool` |  |
| `arrears_reminder_days_before` | `int4` |  |
| `restrict_voting_on_arrears` | `bool` |  |
| `restrict_welfare_claims_on_arrears` | `bool` |  |

## Table `associationmemberduesstanding`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `cycles_paid_ahead` | `int4` |  |
| `consecutive_missed_cycles` | `int4` |  |
| `outstanding_arrears_balance` | `int8` |  Nullable |
| `is_in_arrears` | `bool` |  |
| `is_suspended` | `bool` |  |
| `last_payment_date` | `int8` |  Nullable |
| `next_due_date` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |

## Table `billsplitconfig`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `total_bill_amount` | `int8` |  Nullable |
| `split_mode` | `varchar` |  |
| `settlement_deadline` | `int8` |  Nullable |
| `bill_category` | `varchar` |  |
| `payout_destination_type` | `varchar` |  |
| `payee_identifier` | `varchar` |  Nullable |
| `payee_name` | `varchar` |  Nullable |
| `bill_receipt_url` | `varchar` |  Nullable |
| `created_at` | `int8` |  Nullable |

## Table `billsplitoperationalsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `allow_tip_or_extra` | `bool` |  |
| `auto_close_on_settlement` | `bool` |  |
| `send_reminder_hours_before` | `int4` |  |
| `enable_late_fees` | `bool` |  |
| `late_fee_amount` | `int8` |  Nullable |
| `grace_period_hours` | `int4` |  |
| `is_settled` | `bool` |  |
| `total_collected` | `int8` |  Nullable |
| `total_tip_collected` | `int8` |  Nullable |
| `settled_at` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |

## Table `billsplitmembershare`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `assigned_amount` | `int8` |  Nullable |
| `amount_paid` | `int8` |  Nullable |
| `tip_paid` | `int8` |  Nullable |
| `is_settled` | `bool` |  |
| `paid_at` | `int8` |  Nullable |
| `payment_reference` | `varchar` |  Nullable |
| `created_at` | `int8` |  Nullable |

## Table `investmentclubloan`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `principal_amount` | `int8` |  Nullable |
| `interest_rate_pct` | `float8` |  |
| `total_due_amount` | `int8` |  Nullable |
| `amount_repaid` | `int8` |  Nullable |
| `early_discount_applied` | `int8` |  Nullable |
| `status` | `varchar` |  |
| `guarantors_count` | `int4` |  |
| `due_date` | `int8` |  Nullable |
| `disbursed_at` | `int8` |  Nullable |
| `settled_at` | `int8` |  Nullable |
| `approved_by` | `uuid` |  Nullable |
| `created_at` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |

## Table `associationduesexemption`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `exemption_type` | `varchar` |  |
| `reason` | `varchar` |  |
| `notes` | `varchar` |  Nullable |
| `discount_percentage` | `int4` |  |
| `start_date` | `int8` |  Nullable |
| `end_date` | `int8` |  Nullable |
| `is_active` | `bool` |  |
| `approved_by` | `uuid` |  Nullable |
| `created_at` | `int8` |  Nullable |
| `updated_at` | `int8` |  Nullable |

## Table `ledgerentry`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  Nullable |
| `obligation_id` | `int4` |  Nullable |
| `payout_id` | `int4` |  Nullable |
| `penalty_id` | `int4` |  Nullable |
| `source_account` | `varchar` |  |
| `destination_account` | `varchar` |  |
| `amount` | `int8` |  Nullable |
| `currency` | `varchar` |  |
| `transaction_type` | `varchar` |  |
| `external_reference_id` | `varchar` |  Nullable |
| `status` | `varchar` |  |
| `created_at` | `int8` |  Nullable |
| `settled_at` | `int8` |  Nullable |
| `rotating_payout_id` | `uuid` |  Nullable |
| `rotating_collection_id` | `uuid` |  Nullable |

## Table `command_idempotency`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `user_id` | `uuid` |  |
| `client_request_id` | `varchar` |  |
| `status` | `varchar` |  |
| `response_code` | `int4` |  |
| `response_json` | `text` |  |
| `created_at` | `int8` |  |

## Table `audit_event`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `event_id` | `uuid` | Primary |
| `actor_user_id` | `uuid` |  Nullable |
| `action` | `varchar` |  |
| `entity_type` | `varchar` |  |
| `entity_id` | `varchar` |  |
| `payload_json` | `text` |  |
| `previous_hash` | `varchar` |  |
| `current_hash` | `varchar` |  |
| `created_at` | `int8` |  |
| `tenant_group_id` | `varchar` |  Nullable |
| `request_id` | `uuid` |  Nullable |
| `source` | `text` |  |

## Table `payoutsignature`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `payout_id` | `int4` |  |
| `signer_user_id` | `uuid` |  |
| `signer_role` | `varchar` |  |
| `status` | `varchar` |  |
| `device_fingerprint` | `varchar` |  Nullable |
| `pin_verified` | `bool` |  |
| `notes` | `varchar` |  Nullable |
| `signature_timestamp` | `int8` |  Nullable |

## Table `rotatingcyclereport`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `report_id` | `varchar` |  |
| `group_id` | `varchar` |  |
| `cycle_number` | `int4` |  |
| `report_type` | `varchar` |  |
| `expected_pool_target` | `int8` |  Nullable |
| `actual_collected_amount` | `int8` |  Nullable |
| `collection_rate_percentage` | `float8` |  |
| `gross_payout_amount` | `int8` |  Nullable |
| `early_security_hold_deducted` | `int8` |  Nullable |
| `net_payout_disbursed` | `int8` |  Nullable |
| `recipient_user_id` | `uuid` |  |
| `recipient_name` | `varchar` |  |
| `recipient_turn_position` | `int4` |  |
| `report_data` | `json` |  Nullable |
| `ledger_entries_count` | `int4` |  |
| `cryptographic_hash_sha256` | `varchar` |  |
| `certified_by` | `varchar` |  |
| `generated_at` | `int8` |  Nullable |

## Table `targetsavingspayoutproposal`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `created_by_user_id` | `uuid` |  |
| `provider_name` | `varchar` |  |
| `account_type` | `varchar` |  |
| `account_number` | `varchar` |  |
| `account_name` | `varchar` |  |
| `status` | `varchar` |  |
| `created_at` | `int8` |  Nullable |

## Table `targetsavingspayoutapproval`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `proposal_id` | `uuid` | Primary |
| `user_id` | `uuid` | Primary |
| `approved` | `bool` |  |
| `created_at` | `int8` |  Nullable |

## Table `groupcommonsettings`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `int4` | Primary |
| `group_id` | `varchar` |  |
| `allow_partial_payments` | `bool` |  |
| `minimum_partial_payment_amount` | `float8` |  Nullable |
| `minimum_kyc_tier` | `int4` |  |
| `group_start_time` | `int8` |  Nullable |
| `require_guarantor` | `bool` |  |
| `maximum_member_capacity` | `int4` |  Nullable |
| `collection_frequency_days` | `int4` |  Nullable |
| `grace_period_hours` | `int4` |  |
| `late_payment_policy` | `varchar` |  |
| `payment_approval_threshold` | `int8` |  Nullable |
| `allow_advance_payments` | `bool` |  |
| `updated_at` | `int8` |  Nullable |

## Table `groupfinancialreport`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `report_id` | `varchar` | Primary |
| `group_id` | `varchar` |  |
| `requester_user_id` | `uuid` |  |
| `period_type` | `varchar` |  |
| `selected_date` | `date` |  |
| `start_date` | `date` |  |
| `end_date` | `date` |  |
| `included_sections` | `json` |  |
| `payload` | `json` |  |
| `created_at` | `timestamptz` |  |

## Table `groupreportsectionvisibility`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `group_id` | `varchar` | Primary |
| `section_key` | `varchar` | Primary |
| `visible_to_members` | `bool` |  |
| `updated_by` | `uuid` |  Nullable |
| `updated_at` | `timestamptz` |  |

## Table `notification`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `recipient_user_id` | `uuid` |  |
| `actor_user_id` | `uuid` |  Nullable |
| `event_type` | `varchar` |  |
| `category` | `varchar` |  |
| `title` | `varchar` |  |
| `preview` | `varchar` |  Nullable |
| `body` | `text` |  |
| `source_type` | `varchar` |  Nullable |
| `source_id` | `varchar` |  Nullable |
| `payload` | `json` |  |
| `can_reply` | `bool` |  |
| `dedupe_key` | `varchar` |  Nullable |
| `created_at` | `timestamptz` |  |
| `read_at` | `timestamptz` |  Nullable |
| `group_id` | `varchar` |  Nullable |

## Table `notificationreply`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `notification_id` | `uuid` |  |
| `sender_user_id` | `uuid` |  |
| `parent_reply_id` | `uuid` |  Nullable |
| `body` | `text` |  |
| `created_at` | `timestamptz` |  |

## Table `rotating_cycle`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `cycle_number` | `int4` |  |
| `starts_at` | `timestamptz` |  |
| `ends_at` | `timestamptz` |  |
| `collection_start_time` | `time` |  |
| `collection_end_time` | `time` |  |
| `timezone_name` | `text` |  |
| `expected_pool_amount` | `numeric` |  |
| `actual_collected_amount` | `numeric` |  |
| `reserve_percentage` | `numeric` |  |
| `reserve_amount` | `numeric` |  |
| `available_payout_amount` | `numeric` |  |
| `collection_rate_percentage` | `numeric` |  |
| `status` | `text` |  |
| `payout_readiness_status` | `text` |  |
| `closed_at` | `timestamptz` |  Nullable |
| `completed_at` | `timestamptz` |  Nullable |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Table `rotating_daily_collection`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `cycle_id` | `uuid` |  |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `collection_date` | `date` |  |
| `window_start` | `timestamptz` |  |
| `window_end` | `timestamptz` |  |
| `amount_due` | `numeric` |  |
| `amount_paid` | `numeric` |  |
| `status` | `text` |  |
| `payment_reference` | `text` |  Nullable |
| `paid_at` | `timestamptz` |  Nullable |
| `late_at` | `timestamptz` |  Nullable |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Table `rotating_payout`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `cycle_id` | `uuid` |  |
| `group_id` | `varchar` |  |
| `cycle_number` | `int4` |  |
| `gross_pool_amount` | `numeric` |  |
| `reserve_amount` | `numeric` |  |
| `net_payout_amount` | `numeric` |  |
| `recipient_count` | `int4` |  |
| `amount_per_recipient` | `numeric` |  Nullable |
| `status` | `text` |  |
| `hold_reason` | `text` |  Nullable |
| `approval_required` | `bool` |  |
| `required_approval_count` | `int4` |  |
| `approved_count` | `int4` |  |
| `created_at` | `timestamptz` |  |
| `approved_at` | `timestamptz` |  Nullable |
| `disbursed_at` | `timestamptz` |  Nullable |
| `failed_at` | `timestamptz` |  Nullable |
| `updated_at` | `timestamptz` |  |

## Table `rotating_payout_recipient`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `payout_id` | `uuid` |  |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `turn_position` | `int4` |  |
| `amount` | `numeric` |  |
| `payout_destination_id` | `varchar` |  Nullable |
| `status` | `text` |  |
| `external_reference_id` | `text` |  Nullable |
| `disbursed_at` | `timestamptz` |  Nullable |
| `created_at` | `timestamptz` |  |

## Table `rotating_reserve_entry`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `cycle_id` | `uuid` |  |
| `amount` | `numeric` |  |
| `currency_code` | `varchar` |  |
| `reason` | `text` |  |
| `status` | `text` |  |
| `created_at` | `timestamptz` |  |
| `released_at` | `timestamptz` |  Nullable |

## Table `rotating_turn_swap`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `requester_user_id` | `uuid` |  |
| `target_user_id` | `uuid` |  |
| `requester_cycle_number` | `int4` |  |
| `target_cycle_number` | `int4` |  |
| `status` | `text` |  |
| `approved_at` | `timestamptz` |  Nullable |
| `applied_at` | `timestamptz` |  Nullable |
| `created_at` | `timestamptz` |  |
| `updated_at` | `timestamptz` |  |

## Table `group_role_grant`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `role_code` | `text` |  |
| `granted_by_user_id` | `uuid` |  |
| `status` | `text` |  |
| `granted_at` | `timestamptz` |  |
| `expires_at` | `timestamptz` |  Nullable |
| `revoked_at` | `timestamptz` |  Nullable |
| `revoked_by_user_id` | `uuid` |  Nullable |
| `reason` | `text` |  Nullable |

## Table `group_permission_grant`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `group_id` | `varchar` |  |
| `user_id` | `uuid` |  |
| `permission_code` | `text` |  |
| `granted_by_user_id` | `uuid` |  |
| `status` | `text` |  |
| `granted_at` | `timestamptz` |  |
| `expires_at` | `timestamptz` |  Nullable |
| `revoked_at` | `timestamptz` |  Nullable |

## Table `payment_webhook_event`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `provider_name` | `text` |  |
| `provider_event_id` | `text` |  |
| `event_type` | `text` |  |
| `payload_hash` | `text` |  |
| `payload` | `jsonb` |  |
| `status` | `text` |  |
| `received_at` | `timestamptz` |  |
| `processed_at` | `timestamptz` |  Nullable |
| `failure_reason` | `text` |  Nullable |

## Table `backend_job_execution`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `id` | `uuid` | Primary |
| `job_type` | `text` |  |
| `idempotency_key` | `text` |  |
| `group_id` | `varchar` |  Nullable |
| `cycle_id` | `uuid` |  Nullable |
| `status` | `text` |  |
| `attempts` | `int4` |  |
| `available_at` | `timestamptz` |  |
| `locked_at` | `timestamptz` |  Nullable |
| `locked_by` | `text` |  Nullable |
| `last_error` | `text` |  Nullable |
| `created_at` | `timestamptz` |  |
| `completed_at` | `timestamptz` |  Nullable |

## Table `permission_catalog`

### Columns

| Name | Type | Constraints |
|------|------|-------------|
| `permission_code` | `text` | Primary |
| `description` | `text` |  |

## RLS Policies

### `rotating_daily_collection`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `rotating_daily_collection_member_read` | SELECT | public | PERMISSIVE | `is_group_member(group_id)` | — |
| `rotating_collection_member_read` | SELECT | public | PERMISSIVE | `(is_active_group_member(group_id) AND (user_id = auth.uid()))` | — |
| `rotating_collection_owner_read` | SELECT | public | PERMISSIVE | `(user_id = auth.uid())` | — |

### `rotating_turn_swap`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `rotating_turn_swap_member_read` | SELECT | public | PERMISSIVE | `is_group_member(group_id)` | — |
| `rotating_swap_member_read` | SELECT | public | PERMISSIVE | `is_active_group_member(group_id)` | — |

### `rotating_payout_recipient`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `rotating_recipient_member_read` | SELECT | public | PERMISSIVE | `is_active_group_member(group_id)` | — |
| `rotating_payout_recipient_member_read` | SELECT | public | PERMISSIVE | `is_active_group_member(group_id)` | — |

### `group_role_grant`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `role_grant_member_read` | SELECT | public | PERMISSIVE | `is_active_group_member(group_id)` | — |

### `group_permission_grant`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `permission_grant_member_read` | SELECT | public | PERMISSIVE | `is_active_group_member(group_id)` | — |

### `rotating_cycle`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `rotating_cycle_member_read` | SELECT | public | PERMISSIVE | `is_active_group_member(group_id)` | — |

### `rotating_payout`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `rotating_payout_member_read` | SELECT | public | PERMISSIVE | `is_active_group_member(group_id)` | — |

### `rotating_reserve_entry`

| Policy | Command | Roles | Action | USING | WITH CHECK |
|--------|---------|-------|--------|-------|------------|
| `rotating_reserve_member_read` | SELECT | public | PERMISSIVE | `is_active_group_member(group_id)` | — |
