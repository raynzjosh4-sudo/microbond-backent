from datetime import datetime
from sqlalchemy.orm import Session

from app.models.group.group import GroupMembership
from app.services.group.matrix_generators.standard_fixed import generate_standard_fixed_matrix
from app.services.group.matrix_generators.auction_bidding import generate_auction_bidding_matrix


def route_matrix_generation(
    session: Session,
    group_id: str,
    group_type: str,
    members: list[GroupMembership],
    settings,
    details,
    start_date: datetime
):
    """
    The Strategy Traffic Cop: Routes the matrix generation to the correct isolated function.
    """
    strat = (group_type or "").upper().strip()

    if "TRUST" in strat or strat == "SMART_TRUST":
        from app.models.user.user import User
        user_ids = [m.user_id for m in members]
        users = session.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}

        members.sort(
            key=lambda m: user_map[m.user_id].trust_score if (m.user_id in user_map and user_map[m.user_id].trust_score) else 50,
            reverse=True
        )
        return generate_standard_fixed_matrix(session, group_id, members, settings, details, start_date)

    elif "BID" in strat or "AUCTION" in strat:
        return generate_auction_bidding_matrix(session, group_id, members, settings, details, start_date)

    elif "RANDOM" in strat:
        import random
        random.shuffle(members)
        return generate_standard_fixed_matrix(session, group_id, members, settings, details, start_date)

    else:
        return generate_standard_fixed_matrix(session, group_id, members, settings, details, start_date)
