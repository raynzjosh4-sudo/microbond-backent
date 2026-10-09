from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session
import io
import zipfile
import csv

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout

router = APIRouter(prefix="/api/v1/groups", tags=["Group Data Export"])

@router.get("/{group_id}/membership/me/export", summary="Export personal group records as ZIP")
def export_my_records(
    group_id: str,
    include_chat_history: bool = Query(False, description="Whether to include group chat history"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify membership
    membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="You are not a member of this group.")

    # 2. Fetch Personal Financial Data
    obligations = session.query(MemberObligation).filter_by(
        group_id=group_id, user_id=current_user.id
    ).order_by(MemberObligation.cycle_number).all()

    payouts = session.query(GroupPayout).filter_by(
        group_id=group_id, user_id=current_user.id
    ).order_by(GroupPayout.cycle_number).all()

    # 3. Build ZIP file in-memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # A. Ledger: Obligations (CSV)
        obs_csv = io.StringIO()
        writer = csv.writer(obs_csv)
        writer.writerow(["Cycle Number", "Amount Due", "Amount Paid", "Status"])
        for ob in obligations:
            writer.writerow([ob.cycle_number, f"{ob.amount_due:.2f}", f"{ob.amount_paid:.2f}", ob.status])
            
        zip_file.writestr("my_contributions_ledger.csv", obs_csv.getvalue())
        
        # B. Ledger: Payouts (CSV)
        payouts_csv = io.StringIO()
        pwriter = csv.writer(payouts_csv)
        pwriter.writerow(["Cycle Number", "Amount Expected", "Amount Received", "Status"])
        for p in payouts:
            pwriter.writerow([p.cycle_number, f"{p.amount_expected:.2f}", f"{p.amount_received:.2f}", p.status])
            
        zip_file.writestr("my_payouts_ledger.csv", payouts_csv.getvalue())

        # C. Professional HTML Report
        html_content = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px; color: #333; }}
                h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                h2 {{ color: #2980b9; margin-top: 30px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; color: #333; font-weight: 600; text-transform: uppercase; font-size: 0.9em; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .status-PENDING {{ color: #f39c12; font-weight: bold; }}
                .status-COMPLETED {{ color: #27ae60; font-weight: bold; }}
                .status-PAID {{ color: #27ae60; font-weight: bold; }}
                .status-LATE {{ color: #e74c3c; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Microbond Financial Ledger</h1>
            <p><strong>Member ID:</strong> {current_user.id}</p>
            <p><strong>Group ID:</strong> {group_id}</p>
            
            <h2>My Contributions</h2>
            <table>
                <tr><th>Cycle</th><th>Amount Due</th><th>Amount Paid</th><th>Status</th></tr>
                {"".join([f"<tr><td>{ob.cycle_number}</td><td>${ob.amount_due:.2f}</td><td>${ob.amount_paid:.2f}</td><td class='status-{ob.status}'>{ob.status}</td></tr>" for ob in obligations])}
            </table>

            <h2>My Payouts</h2>
            <table>
                <tr><th>Cycle</th><th>Expected</th><th>Received</th><th>Status</th></tr>
                {"".join([f"<tr><td>{p.cycle_number}</td><td>${p.amount_expected:.2f}</td><td>${p.amount_received:.2f}</td><td class='status-{p.status}'>{p.status}</td></tr>" for p in payouts])}
            </table>
        </body>
        </html>
        """
        zip_file.writestr("Professional_Ledger_Report.html", html_content)

        # C. Interactive Chat History (HTML with Chart.js)
        if include_chat_history:
            # Mock data representing a chart message in the chat
            mock_chart_data = {
                "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                "datasets": [{
                    "label": "Total Group Pool ($)",
                    "data": [500, 1000, 1500, 2000],
                    "borderColor": "#3498db",
                    "backgroundColor": "rgba(52, 152, 219, 0.2)",
                    "fill": True,
                    "tension": 0.4
                }]
            }
            import json
            chart_json = json.dumps(mock_chart_data)

            chat_html = f"""
            <html>
            <head>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background-color: #f4f7f6; }}
                    .chat-container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }}
                    .message {{ margin-bottom: 20px; padding: 15px; border-radius: 8px; background-color: #f8f9fa; border-left: 4px solid #bdc3c7; }}
                    .message.system {{ border-left-color: #3498db; background-color: #ebf5fb; }}
                    .sender {{ font-weight: bold; color: #2c3e50; margin-bottom: 5px; }}
                    .time {{ font-size: 0.8em; color: #7f8c8d; float: right; }}
                    .chart-wrapper {{ width: 100%; max-width: 600px; margin-top: 15px; background: white; padding: 10px; border-radius: 8px; border: 1px solid #eee; }}
                </style>
            </head>
            <body>
                <div class="chat-container">
                    <h2 style="text-align: center; color: #2c3e50; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px;">Group Chat History</h2>
                    
                    <div class="message">
                        <span class="time">10:00 AM</span>
                        <div class="sender">Admin</div>
                        <div>Welcome to the group! Let's hit our target!</div>
                    </div>

                    <div class="message system">
                        <span class="time">10:05 AM</span>
                        <div class="sender">Microbond Bot (System)</div>
                        <div>Here is the latest projection chart for our savings pool:</div>
                        
                        <!-- Interactive Chart Canvas -->
                        <div class="chart-wrapper">
                            <canvas id="savingsChart"></canvas>
                        </div>
                    </div>
                </div>

                <script>
                    // Render the chart dynamically using the injected JSON data
                    const ctx = document.getElementById('savingsChart').getContext('2d');
                    const chartData = {chart_json};
                    
                    new Chart(ctx, {{
                        type: 'line',
                        data: chartData,
                        options: {{
                            responsive: true,
                            plugins: {{
                                title: {{ display: true, text: 'Monthly Savings Projection' }}
                            }}
                        }}
                    }});
                </script>
            </body>
            </html>
            """
            zip_file.writestr("chat_history_interactive.html", chat_html)

    # 4. Stream response back to user
    zip_buffer.seek(0)
    
    headers = {
        "Content-Disposition": f"attachment; filename=Microbond_Group_{group_id}_Records.zip"
    }
    
    return StreamingResponse(
        zip_buffer, 
        media_type="application/zip",
        headers=headers
    )
