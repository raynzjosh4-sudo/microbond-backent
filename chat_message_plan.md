# Group Chat Integration Plan

This document maps out all the existing APIs in the Microbond backend and defines how they will inject system messages into the unified Group Chat. By doing this, the chat becomes the **central nervous system** of the group—members won't need to check 5 different tabs because every important event is broadcasted in the chat room.

## 1. Membership & Joining APIs
When users interact with the group roster, the following messages should be sent to the chat.

| API Trigger | `message_type` | Example `message_text` | Broadcast Trigger |
| :--- | :--- | :--- | :--- |
| `POST /join/request` | `SYSTEM_EVENT` | "Alice has requested to join the group." | Sent to Admins only (or group if public) |
| `POST /membership/add_member` | `SYSTEM_EVENT` | "Admin added Bob to the group. Welcome Bob!" | Broadcasted to the whole group |
| `POST /membership/leave_group` | `SYSTEM_EVENT` | "Charlie has left the group." | Broadcasted to the whole group |
| `POST /membership/vouching` | `TRUST_EVENT` | "Diana vouched for Eve (Trust Score +10)" | Broadcasted to the whole group |

## 2. Financial & Contributions (Target Savings / Rotating)
Money is the most sensitive part of the app. Every financial action must leave an audit trail in the chat.

| API Trigger | `message_type` | Example `message_text` | Extra Payload Data |
| :--- | :--- | :--- | :--- |
| `POST /finance/contribute` | `TRANSACTION` | "Frank contributed $50 to the group wallet." | `{"amount": 50, "currency": "USD"}` |
| `POST /finance/payout` | `PAYOUT_EVENT` | "It's Grace's turn! $500 has been paid out." | `{"recipient_id": "...", "amount": 500}` |
| `POST /rotating/turn_swaps` | `SYSTEM_EVENT` | "Henry and Ian swapped their payout turns." | `{"user_a": "Henry", "user_b": "Ian"}` |
| `POST /membership/payment_method`| `SYSTEM_EVENT` | "The admin updated the group payment method." | None |

## 3. Reports & Analytics APIs
When your backend crunches data, it should present it beautifully in the chat.

| API Trigger | `message_type` | Example `message_text` | Extra Payload Data (Graph Data) |
| :--- | :--- | :--- | :--- |
| `GET /report/weekly_report` (Cron Job) | `REPORT_CARD` | "Weekly Summary: $1,200 collected, 0 defaults." | `{"collected": 1200, "defaults": 0, "chart_url": "..."}` |
| `POST /report/submit_report` | `USER_REPORT` | "Jack reported a discrepancy in his payout." | `{"report_id": 45}` |

## 4. Governance & Settings APIs
When group rules change, members must be notified immediately.

| API Trigger | `message_type` | Example `message_text` | Broadcast Trigger |
| :--- | :--- | :--- | :--- |
| `PATCH /settings/profile` | `SYSTEM_EVENT` | "Admin changed the group name to 'Saving Kings'." | Broadcasted on success |
| `PATCH /settings/permissions` | `SYSTEM_EVENT` | "Admin enabled 'Members can invite others'." | Broadcasted on success |
| `PATCH /settings/financial` | `SYSTEM_EVENT` | "The weekly contribution was increased to $100."| Broadcasted on success |

---

## How to implement this in the code
In any of the API endpoints listed above, you just need to add **3 lines of code** right before you return the response:

```python
from app.api.routes.group.chat.messages import send_chat_message, SendMessageRequest

# 1. Inside your API, create the system message payload
system_msg = SendMessageRequest(
    client_message_id=str(uuid.uuid4()), # Generate a random UUID
    message_type="SYSTEM_EVENT",
    message_text=f"{current_user.full_name} joined the group!"
)

# 2. Call the chat API function internally
await send_chat_message(group_id=group_id, request=system_msg, session=session, current_user=system_user)
```

*(Note: We will create a `get_system_user()` function to represent the "System/Bot" so that these messages aren't tied to a specific human's ID).*
