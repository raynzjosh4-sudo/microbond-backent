After the invitation pages, the joining flow needs several other actions. The invitation page is only the beginning.

## 1. Admin invitation actions

On the admin side, the group administrator should be able to:

- Invite by phone number
- Generate an invite link
- Copy the link
- Share by SMS or WhatsApp
- Resend the invitation
- Cancel the invitation
- Change the invitation expiry
- See whether the invitation was opened
- See whether the invitee verified their phone
- See whether the invitee submitted KYC
- See whether the guarantor accepted
- Approve or reject the joining request

The status could be:

```text
Created
Sent
Opened
Phone verified
Profile incomplete
Waiting for guarantor
Waiting for member votes
Waiting for admin approval
Approved
Rejected
Expired
Cancelled
```

## 2. Invitee actions

On the invitee’s side, the person should be able to:

- Open the secure invitation link
- View the group name and group image
- View the contribution rules
- View the collection time
- View whether a guarantor is required
- View whether admin approval is required
- View whether member voting is required
- Accept the invitation
- Decline the invitation
- Verify their phone
- Complete their profile
- Submit identity verification
- Select a guarantor
- Submit the joining request
- View the progress of the request
- Cancel the request before approval

The invitee should not enter the group chat immediately. They first need to complete the required conditions.

## 3. Guarantor actions

If a guarantor is required, the selected guarantor should receive a notification and be able to:

- View who selected them
- View the group name
- View the joining member’s permitted information
- Read the guarantor responsibilities
- Accept the guarantor request
- Decline the guarantor request
- Ask the applicant to select another guarantor

Possible guarantor statuses:

```text
Not selected
Request sent
Viewed
Accepted
Declined
Expired
Cancelled
```

The invitee cannot proceed if the group requires a guarantor and the guarantor has not accepted.

## 4. Member voting actions

If voting is enabled, eligible members should see a new-member voting page.

They can:

- View the applicant’s permitted information
- See phone verification status
- See KYC status or level
- See guarantor status
- Approve the applicant
- Reject the applicant
- Abstain, if your rules allow abstention
- View the current vote count
- See when the voting period ends

Example:

```text
4 of 5 approvals
2 members have not voted
Voting closes in 18 hours
```

A member must not vote twice. The database should enforce:

```text
one vote per member per joining request
```

Members should not see private voter identities unless you deliberately allow that.

## 5. Admin approval actions

The admin’s pending-members page should show:

```text
Daniel K.
Phone: Verified
Identity: Submitted
Guarantor: Accepted
Votes: 4 of 5
```

Admin actions:

- Approve
- Reject
- Request more information
- Extend the review period
- Cancel the request
- View permitted details
- View the applicant’s guarantor
- View the voting result

If both voting and admin approval are enabled, the member should become active only when both conditions pass:

```text
Required votes reached
AND
Admin approved
AND
Guarantor accepted
AND
Required verification completed
```

## 6. Invitee request-status page

The invitee needs a page showing exactly what is complete and what is pending:

```text
Phone verification       Complete
Profile                  Complete
Government ID             Submitted
Guarantor                 Accepted
Member votes              4 of 5
Admin approval            Waiting
```

This page should update automatically or through a refresh action.

Useful actions:

- View requirements
- View group rules
- Cancel request
- Replace guarantor
- Contact admin
- Leave the process

## 7. Final approval action

When everything is complete, the system should:

1. Change the joining request to `APPROVED`.
2. Create a `groupmembership` record.
3. Set membership status to `ACTIVE`.
4. Assign the member’s role.
5. Assign a payout position if applicable.
6. Add the member to the group member list.
7. Create any required first-cycle obligations.
8. Notify the new member.
9. Notify the admin and guarantor.
10. Allow access to the group chat.

The member should not be marked active before the membership record is successfully created.

## 8. Rejection and expiry actions

### Rejected request

The applicant should see:

```text
Your request was not approved.
```

Possible actions:

- View general reason
- Contact admin
- Request a new invitation
- Close the page

Do not expose private voter comments or private voter identities automatically.

### Expired invitation

The invitee should see:

```text
This invitation has expired or is no longer available.
```

Actions:

- Request a new invitation
- Contact the group admin
- Close

### Cancelled invitation

The invitee should see:

```text
This invitation was cancelled by the group.
```

They should not be able to continue using the old link.

## 9. Important distinction

There are three different objects in the flow:

```text
Invitation
Joining request
Active membership
```

They should not be treated as the same thing.

### Invitation

Created by an admin and sent to a person.

```text
INVITE_CREATED
INVITE_OPENED
INVITE_ACCEPTED
INVITE_EXPIRED
INVITE_CANCELLED
```

### Joining request

Created when the invitee accepts and begins the process.

```text
DRAFT
PHONE_VERIFIED
KYC_SUBMITTED
GUARANTOR_PENDING
GUARANTOR_ACCEPTED
VOTING
ADMIN_REVIEW
APPROVED
REJECTED
CANCELLED
```

### Active membership

Created only after approval.

```text
ACTIVE
SUSPENDED
LEFT
REMOVED
```

This separation is very important. A person can open an invitation without becoming a member, and they can submit a joining request without being approved.