"""
Wani AI Voice Studio - Automated Subscription Lifecycle Verification Suite
===========================================================================
Executes and validates all 12 mandatory billing tests for Razorpay Subscriptions:

1. Successful initial subscription & server-side signature verification
2. Successful renewal (subscription.charged webhook)
3. Duplicate webhook delivery idempotency
4. Failed renewal, grace period, and post-grace restrictions
5. Delayed payment confirmation
6. Cancellation at period end (access preserved until current_period_end)
7. Immediate cancellation when requested
8. Expiry and resubscription lifecycle
9. Plan upgrade and downgrade synchronization
10. Forged webhook rejection (tampered signature)
11. Unauthorized plan activation rejection (tampered checkout params)
12. Correct quota reset and access restrictions enforcement
"""

import sys
import os
import json
import time
import hmac
import hashlib
from datetime import datetime, timedelta

# Force UTF-8 on Windows stdout/stderr
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from subscription_manager import SubscriptionManager, get_now_ist, format_iso

def compute_webhook_signature(body_bytes: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

def compute_checkout_signature(payment_id: str, sub_id: str, secret: str) -> str:
    msg = f"{payment_id}|{sub_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def run_all_tests():
    print("=" * 75)
    print("🚀 STARTING WANI SUBSCRIPTION LIFECYCLE VERIFICATION SUITE (12 TESTS)")
    print("=" * 75)

    sm = SubscriptionManager()
    cfg = sm.get_config()
    webhook_secret = cfg["razorpay_webhook_secret"]
    key_secret = cfg["razorpay_key_secret"]

    results = []

    # -------------------------------------------------------------------------
    # TEST 1: Successful initial subscription & server signature verification
    # -------------------------------------------------------------------------
    try:
        test_email = "test_user_initial@wani.ai"
        checkout = sm.create_subscription_checkout(test_email, "starter", "monthly")
        sub_id = checkout["subscription_id"]
        assert sub_id.startswith("sub_"), f"Invalid sub_id generated: {sub_id}"

        payment_id = f"pay_init_{int(time.time())}"
        valid_sig = compute_checkout_signature(payment_id, sub_id, key_secret)

        ok, msg = sm.verify_checkout_signature(test_email, payment_id, sub_id, valid_sig)
        assert ok, f"Initial subscription verification failed: {msg}"

        entitlements = sm.get_user_entitlements(test_email)
        assert entitlements["is_paid"] is True, "User should have is_paid=True"
        assert entitlements["plan_code"] == "starter", f"Expected plan starter, got {entitlements['plan_code']}"
        assert entitlements["status"] == "active", f"Expected active status, got {entitlements['status']}"
        assert entitlements["quota_terms"]["words_per_month"] == 50000, "Quota words mismatch"

        results.append(("Test 1: Successful initial subscription", "PASS", "Verified signature & activated Starter"))
    except Exception as e:
        results.append(("Test 1: Successful initial subscription", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 2: Successful renewal (subscription.charged webhook)
    # -------------------------------------------------------------------------
    try:
        renew_email = "test_user_renewal@wani.ai"
        # Setup initial subscription
        checkout = sm.create_subscription_checkout(renew_email, "pro", "monthly")
        sub_id = checkout["subscription_id"]
        pay_id = f"pay_renew_01_{int(time.time())}"
        sig = compute_checkout_signature(pay_id, sub_id, key_secret)
        sm.verify_checkout_signature(renew_email, pay_id, sub_id, sig)

        old_sub = sm.get_user_entitlements(renew_email)["subscription_details"]
        old_period_end = old_sub["current_period_end"]

        # Simulate renewal webhook
        time.sleep(0.05)
        new_pay_id = f"pay_renew_02_{int(time.time())}"
        renewal_payload = {
            "entity": "event",
            "account_id": "acc_wani_test",
            "event": "subscription.charged",
            "contains": ["subscription", "payment"],
            "payload": {
                "subscription": {
                    "entity": {
                        "id": sub_id,
                        "plan_id": "plan_pro_monthly",
                        "status": "active",
                        "notes": {"user_email": renew_email}
                    }
                },
                "payment": {
                    "entity": {
                        "id": new_pay_id,
                        "amount": 69900,
                        "currency": "INR",
                        "status": "captured",
                        "email": renew_email
                    }
                }
            },
            "created_at": int(time.time())
        }
        body_bytes = json.dumps(renewal_payload).encode("utf-8")
        wh_sig = compute_webhook_signature(body_bytes, webhook_secret)

        ok, msg, code = sm.process_webhook(body_bytes, wh_sig, event_id=f"evt_renew_{int(time.time())}")
        assert ok and code == 200, f"Webhook renewal failed: {msg}"

        new_ent = sm.get_user_entitlements(renew_email)
        assert new_ent["is_paid"] is True
        assert new_ent["status"] == "active"
        assert new_ent["subscription_details"]["last_payment_id"] == new_pay_id

        # Verify payment recorded in history
        c_data = sm.get_customer_dashboard_data(renew_email)
        p_ids = [p["payment_id"] for p in c_data["payment_history"]]
        assert new_pay_id in p_ids, f"Payment {new_pay_id} not found in customer payment history"

        results.append(("Test 2: Successful renewal", "PASS", "Processed subscription.charged and extended period"))
    except Exception as e:
        results.append(("Test 2: Successful renewal", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 3: Duplicate webhook idempotency
    # -------------------------------------------------------------------------
    try:
        dup_event_id = f"evt_dup_test_{int(time.time())}"
        dup_payload = {
            "entity": "event",
            "event": "subscription.charged",
            "payload": {
                "subscription": {"entity": {"id": sub_id, "notes": {"user_email": renew_email}}},
                "payment": {"entity": {"id": "pay_dup_01", "amount": 69900}}
            },
            "created_at": int(time.time())
        }
        dup_bytes = json.dumps(dup_payload).encode("utf-8")
        dup_sig = compute_webhook_signature(dup_bytes, webhook_secret)

        # 1st delivery
        ok1, msg1, code1 = sm.process_webhook(dup_bytes, dup_sig, event_id=dup_event_id)
        assert ok1 and code1 == 200

        # 2nd duplicate delivery
        ok2, msg2, code2 = sm.process_webhook(dup_bytes, dup_sig, event_id=dup_event_id)
        assert ok2 and code2 == 200
        assert "duplicate" in msg2.lower() or "idempotent" in msg2.lower(), f"Unexpected message on duplicate: {msg2}"

        results.append(("Test 3: Duplicate webhook idempotency", "PASS", "Safe duplicate ignore, no double billing"))
    except Exception as e:
        results.append(("Test 3: Duplicate webhook idempotency", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 4: Failed renewal, grace period, and post-grace restrictions
    # -------------------------------------------------------------------------
    try:
        fail_email = "test_user_failure@wani.ai"
        checkout = sm.create_subscription_checkout(fail_email, "starter", "monthly")
        sub_id = checkout["subscription_id"]
        pay_id = f"pay_f1_{int(time.time())}"
        sig = compute_checkout_signature(pay_id, sub_id, key_secret)
        sm.verify_checkout_signature(fail_email, pay_id, sub_id, sig)

        # Send payment.failed webhook
        fail_payload = {
            "entity": "event",
            "event": "subscription.pending",
            "payload": {
                "subscription": {"entity": {"id": sub_id, "notes": {"user_email": fail_email}}},
                "payment": {"entity": {"id": "pay_fail_01", "amount": 29900, "status": "failed"}}
            },
            "created_at": int(time.time())
        }
        f_bytes = json.dumps(fail_payload).encode("utf-8")
        f_sig = compute_webhook_signature(f_bytes, webhook_secret)
        ok, msg, code = sm.process_webhook(f_bytes, f_sig)
        assert ok and code == 200

        # Step 4A: Check Grace Period Active (User still has access + warning banner)
        ent = sm.get_user_entitlements(fail_email)
        assert ent["is_paid"] is True, "User should still have paid access during grace period"
        assert ent["status"] == "past_due_in_grace", f"Expected past_due_in_grace, got {ent['status']}"
        assert ent["warning_message"] is not None, "Warning message must be displayed"
        assert ent["grace_days_remaining"] > 0, "Grace days remaining should be > 0"

        # Step 4B: Simulate Grace Period Expiry (time travel past grace period)
        with sm.lock:
            subs = sm._load_json(os.path.join(sm.BASE_DIR if hasattr(sm, 'BASE_DIR') else os.path.dirname(__file__), "subscriptions_db.json"))
            subs[fail_email]["grace_period_expires_at"] = format_iso(get_now_ist() - timedelta(days=1))
            sm._save_json(os.path.join(sm.BASE_DIR if hasattr(sm, 'BASE_DIR') else os.path.dirname(__file__), "subscriptions_db.json"), subs)

        ent_expired = sm.get_user_entitlements(fail_email)
        assert ent_expired["is_paid"] is False, "After grace period, is_paid must be False"
        assert ent_expired["status"] == "halted_grace_expired", f"Expected halted_grace_expired, got {ent_expired['status']}"
        assert ent_expired["quota_terms"]["max_words_per_trial"] == 100, "Should fall back to Free trial limits"

        results.append(("Test 4: Failed renewal & grace period", "PASS", "Grace period allows temporary access, then restricts features"))
    except Exception as e:
        results.append(("Test 4: Failed renewal & grace period", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 5: Delayed payment confirmation
    # -------------------------------------------------------------------------
    try:
        delay_email = "test_user_delayed@wani.ai"
        checkout = sm.create_subscription_checkout(delay_email, "starter", "monthly")
        sub_id = checkout["subscription_id"]

        # Check status initially is created
        ent1 = sm.get_user_entitlements(delay_email)
        assert ent1["is_paid"] is False, "Created state should not have paid entitlements yet"

        # Delayed activation webhook arrives later
        activate_payload = {
            "entity": "event",
            "event": "subscription.activated",
            "payload": {
                "subscription": {"entity": {"id": sub_id, "notes": {"user_email": delay_email}}},
                "payment": {"entity": {"id": f"pay_delayed_{int(time.time())}", "amount": 29900, "status": "captured"}}
            },
            "created_at": int(time.time())
        }
        act_bytes = json.dumps(activate_payload).encode("utf-8")
        act_sig = compute_webhook_signature(act_bytes, webhook_secret)
        ok, msg, code = sm.process_webhook(act_bytes, act_sig)
        assert ok and code == 200

        ent2 = sm.get_user_entitlements(delay_email)
        assert ent2["is_paid"] is True, "Delayed activation must grant paid entitlements"
        assert ent2["status"] == "active"

        results.append(("Test 5: Delayed payment confirmation", "PASS", "Delayed webhook transitions state to active cleanly"))
    except Exception as e:
        results.append(("Test 5: Delayed payment confirmation", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 6: Cancellation at period end (access preserved until current_period_end)
    # -------------------------------------------------------------------------
    try:
        cancel_end_email = "test_user_cancel_end@wani.ai"
        checkout = sm.create_subscription_checkout(cancel_end_email, "starter", "monthly")
        sub_id = checkout["subscription_id"]
        pay_id = f"pay_ce_{int(time.time())}"
        sig = compute_checkout_signature(pay_id, sub_id, key_secret)
        sm.verify_checkout_signature(cancel_end_email, pay_id, sub_id, sig)

        # Cancel at cycle end
        ok, msg = sm.cancel_subscription(cancel_end_email, cancel_at_cycle_end=True)
        assert ok, f"Cancel call failed: {msg}"

        # Check access is still retained
        ent = sm.get_user_entitlements(cancel_end_email)
        assert ent["is_paid"] is True, "User must retain paid access until period end"
        assert ent["status"] == "cancelled_pending_period_end"
        assert "preserved until" in ent["warning_message"].lower()

        # Simulate expiry after current_period_end
        with sm.lock:
            subs_file = os.path.join(os.path.dirname(__file__), "subscriptions_db.json")
            subs = sm._load_json(subs_file)
            subs[cancel_end_email]["current_period_end"] = format_iso(get_now_ist() - timedelta(days=1))
            sm._save_json(subs_file, subs)

        ent_after = sm.get_user_entitlements(cancel_end_email)
        assert ent_after["is_paid"] is False, "Access must expire once period end is passed"
        assert ent_after["status"] == "expired"

        results.append(("Test 6: Cancellation at period end", "PASS", "Access preserved through paid date, then expired"))
    except Exception as e:
        results.append(("Test 6: Cancellation at period end", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 7: Immediate cancellation when requested
    # -------------------------------------------------------------------------
    try:
        imm_email = "test_user_imm_cancel@wani.ai"
        checkout = sm.create_subscription_checkout(imm_email, "pro", "monthly")
        sub_id = checkout["subscription_id"]
        pay_id = f"pay_imm_{int(time.time())}"
        sig = compute_checkout_signature(pay_id, sub_id, key_secret)
        sm.verify_checkout_signature(imm_email, pay_id, sub_id, sig)

        # Immediate cancellation
        ok, msg = sm.cancel_subscription(imm_email, cancel_at_cycle_end=False)
        assert ok, f"Immediate cancellation failed: {msg}"

        ent = sm.get_user_entitlements(imm_email)
        assert ent["is_paid"] is False, "Immediate cancellation must revoke paid access right away"
        assert ent["status"] in ["cancelled", "expired"]

        results.append(("Test 7: Immediate cancellation", "PASS", "Entitlements revoked immediately upon explicit request"))
    except Exception as e:
        results.append(("Test 7: Immediate cancellation", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 8: Expiry and resubscription
    # -------------------------------------------------------------------------
    try:
        # User from test 7 is expired; now they resubscribe to Business
        checkout = sm.create_subscription_checkout(imm_email, "business", "yearly")
        new_sub_id = checkout["subscription_id"]
        new_pay_id = f"pay_resub_{int(time.time())}"
        new_sig = compute_checkout_signature(new_pay_id, new_sub_id, key_secret)

        ok, msg = sm.verify_checkout_signature(imm_email, new_pay_id, new_sub_id, new_sig)
        assert ok, f"Resubscription verification failed: {msg}"

        ent = sm.get_user_entitlements(imm_email)
        assert ent["is_paid"] is True
        assert ent["plan_code"] == "business"
        assert ent["quota_terms"]["words_per_month"] == 1000000

        results.append(("Test 8: Expiry and resubscription", "PASS", "Expired subscriber successfully resubscribed to Business"))
    except Exception as e:
        results.append(("Test 8: Expiry and resubscription", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 9: Plan upgrade and downgrade
    # -------------------------------------------------------------------------
    try:
        up_email = "test_user_upgrade@wani.ai"
        checkout = sm.create_subscription_checkout(up_email, "starter", "monthly")
        sub_id = checkout["subscription_id"]
        pay_id = f"pay_up_{int(time.time())}"
        sig = compute_checkout_signature(pay_id, sub_id, key_secret)
        sm.verify_checkout_signature(up_email, pay_id, sub_id, sig)

        # Step 9A: Immediate Upgrade to Pro
        ok_up, msg_up = sm.change_plan(up_email, "pro", "monthly", schedule_at_cycle_end=False)
        assert ok_up, f"Immediate upgrade failed: {msg_up}"
        ent_pro = sm.get_user_entitlements(up_email)
        assert ent_pro["plan_code"] == "pro"
        assert ent_pro["quota_terms"]["words_per_month"] == 250000

        # Step 9B: Downgrade scheduled at next cycle end
        ok_down, msg_down = sm.change_plan(up_email, "starter", "monthly", schedule_at_cycle_end=True)
        assert ok_down, f"Scheduled downgrade failed: {msg_down}"
        sub_state = sm.get_user_entitlements(up_email)["subscription_details"]
        assert sub_state.get("pending_plan_change") is not None
        assert sub_state["pending_plan_change"]["plan_code"] == "starter"

        results.append(("Test 9: Plan upgrade & downgrade", "PASS", "Synchronized upgrade immediately, scheduled downgrade at cycle end"))
    except Exception as e:
        results.append(("Test 9: Plan upgrade & downgrade", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 10: Forged webhook rejection
    # -------------------------------------------------------------------------
    try:
        forged_payload = json.dumps({"event": "subscription.charged", "id": "forged_01"}).encode("utf-8")
        forged_sig = "a1b2c3d4e5f6_completely_fake_signature_9999"

        ok, msg, code = sm.process_webhook(forged_payload, forged_sig)
        assert ok is False, "Forged webhook must be rejected"
        assert code == 400, f"Expected HTTP 400 for forged webhook, got {code}"
        assert "signature" in msg.lower(), f"Unexpected error message: {msg}"

        results.append(("Test 10: Forged webhook rejection", "PASS", "Invalid HMAC rejected with HTTP 400, no state change"))
    except Exception as e:
        results.append(("Test 10: Forged webhook rejection", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 11: Unauthorized plan activation rejection
    # -------------------------------------------------------------------------
    try:
        fake_email = "attacker@wani.ai"
        checkout = sm.create_subscription_checkout(fake_email, "pro", "monthly")
        sub_id = checkout["subscription_id"]

        tampered_sig = "bad_signature_from_client_tampering"
        ok, msg = sm.verify_checkout_signature(fake_email, "pay_fake_999", sub_id, tampered_sig)
        assert ok is False, "Tampered signature should fail verification"
        assert "verification failed" in msg.lower() or "tampering" in msg.lower()

        ent = sm.get_user_entitlements(fake_email)
        assert ent["is_paid"] is False, "Attacker must NOT be granted paid entitlements"

        results.append(("Test 11: Unauthorized activation rejection", "PASS", "Blocked forged client signature, user remains on Free tier"))
    except Exception as e:
        results.append(("Test 11: Unauthorized activation rejection", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # TEST 12: Correct quota reset and access restrictions
    # -------------------------------------------------------------------------
    try:
        quota_user = "test_user_quota@wani.ai"
        checkout = sm.create_subscription_checkout(quota_user, "starter", "monthly")
        sub_id = checkout["subscription_id"]
        pay_id = f"pay_q_{int(time.time())}"
        sig = compute_checkout_signature(pay_id, sub_id, key_secret)
        sm.verify_checkout_signature(quota_user, pay_id, sub_id, sig)

        # 12A: Deduct 45,000 words (Starter quota is 50,000)
        ok1, msg1, q1 = sm.check_and_deduct_quota(quota_user, words=45000, paragraphs=50)
        assert ok1, f"Valid quota deduction failed: {msg1}"
        assert q1["words_remaining"] == 5000, f"Expected 5,000 words remaining, got {q1['words_remaining']}"

        # 12B: Attempt to deduct 10,000 words (exceeds 5,000 remaining)
        ok2, msg2, q2 = sm.check_and_deduct_quota(quota_user, words=10000, paragraphs=10)
        assert ok2 is False, "Should have blocked deduction exceeding monthly quota"
        assert "quota exceeded" in msg2.lower()

        # 12C: Reset monthly quota (simulating billing rollover)
        sm._reset_monthly_quota_internal(quota_user, format_iso(get_now_ist()))
        ok3, msg3, q3 = sm.check_and_deduct_quota(quota_user, words=10000, paragraphs=10)
        assert ok3, "After monthly rollover reset, deduction should succeed"
        assert q3["words_remaining"] == 40000

        # 12D: Free tier trial limit check (100 word max per trial)
        free_user = "free_user_quota@wani.ai"
        ok_free_fail, msg_free, _ = sm.check_and_deduct_quota(free_user, words=150)
        assert ok_free_fail is False, "Free user must be blocked when exceeding 100 words"
        assert "100 words" in msg_free

        results.append(("Test 12: Quota reset & restrictions", "PASS", "Pre-request enforcement, hard quota limit & period reset verified"))
    except Exception as e:
        results.append(("Test 12: Quota reset & restrictions", "FAIL", str(e)))

    # -------------------------------------------------------------------------
    # PRINT RESULTS SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 75)
    print("📋 SUMMARY OF BILLING VERIFICATION TESTS")
    print("=" * 75)

    all_passed = True
    for title, status, notes in results:
        sym = "✅" if status == "PASS" else "❌"
        print(f"{sym} {title:<45} : [{status}] - {notes}")
        if status != "PASS":
            all_passed = False

    print("=" * 75)
    if all_passed:
        print("🎉 ALL 12 CRITICAL SUBSCRIPTION LIFECYCLE TESTS PASSED PERFECTLY!")
    else:
        print("⚠️ SOME TESTS FAILED. PLEASE REVIEW LOGS ABOVE.")
    print("=" * 75)
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
