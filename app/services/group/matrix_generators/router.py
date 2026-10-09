from datetime import datetime
from sqlalchemy.orm import Session

from app.models.group.group import GroupMembership
from app.services.group.matrix_generators.standard_fixed import generate_standard_fixed_matrix
from app.services.group.matrix_generators.auction_bidding import generate_auction_bidding_matrix

def route_matrix_generation(session: Session, group_id: str, group_type: str, members: list[GroupMembership], settings, details, start_date: datetime):
    """
    The Strategy Traffic Cop: Routes the matrix generation to the correct isolated function.
    """
    if group_type == "SMART_TRUST":
        # Phase 3: The "Back of the Line" Strategy
        # Sort members by Trust Score Descending to protect the group
        from app.models.user.user import User
        user_ids = [m.user_id for m in members]
        users = session.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}
        
        # Sort members: Highest trust score first. If no trust score, treat as 50 (middle/new user risk).
        # We can also add secondary sorts here later (like lifetime_volume)
        members.sort(
            key=lambda m: user_map[m.user_id].trust_score if user_map[m.user_id].trust_score else 50, 
            reverse=True
        )
        return generate_standard_fixed_matrix(session, group_id, members, settings, details, start_date)
        
    elif group_type == "BIDDING":
        return generate_auction_bidding_matrix(session, group_id, members, settings, details, start_date)
        
    elif group_type == "RANDOM":
        import random
        random.shuffle(members)
        return generate_standard_fixed_matrix(session, group_id, members, settings, details, start_date)
        
    else:
        # Defaults to the standard fixed generator (e.g. FIRST_COME_FIRST_SERVE or ADMIN_ASSIGNED)
        # Assuming `members` is already in the correct order (e.g., ordered by join date in the database query)
        return generate_standard_fixed_matrix(session, group_id, members, settings, details, start_date)
