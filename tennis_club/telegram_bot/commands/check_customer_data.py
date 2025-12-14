from .db_connection import get_db_connection


def check_customer_data(club_card, email, chat_id, is_permission_to_notify):
    """ Check Customer Data """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        club_card = int(club_card)
        email = email.lower()
    except:
        return {"status": "Incorrect ID card", "name":""}

    cursor.execute("""
            SELECT name FROM res_partner
            WHERE club_card=%s AND email=%s AND telegram_chat_id<>0
        """, (club_card, email))
    result = cursor.fetchall()

    if len(result) > 0:
        cursor.close()
        conn.close()
        return {"status": "FAILED", "name":None}

    if is_permission_to_notify:
        cursor.execute("""
                UPDATE res_partner
                SET telegram_chat_id = %s, is_permission_to_notify=TRUE
                WHERE club_card = %s AND email = %s AND (telegram_chat_id IS NULL OR telegram_chat_id = 0)
                RETURNING name
            """, (chat_id, club_card, email))
    else:
        cursor.execute("""
                        UPDATE res_partner
                        SET telegram_chat_id = %s, is_permission_to_notify=FALSE
                        WHERE club_card = %s AND email = %s AND (telegram_chat_id IS NULL OR telegram_chat_id = 0)
                        RETURNING name
                    """, (chat_id, club_card, email))

    updated_rows = cursor.fetchall()
    conn.commit()

    if not updated_rows:
        cursor.close()
        conn.close()
        return {"status": "FAILED", "name": None}

    names = ", ".join(row[0] for row in updated_rows)

    cursor.close()
    conn.close()

    return {"status": "OK", "name": names}
