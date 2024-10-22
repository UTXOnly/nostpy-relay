import psycopg


class ApiQuery:

    async def insert_kind_list(self, conn, cur, kind, allowed, reason, logger):
        try:
                cur.execute(
                    """
                    INSERT INTO allowed_kinds (kind, allowed, reason)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (kind) DO UPDATE 
                    SET allowed = EXCLUDED.allowed, 
                        reason = EXCLUDED.reason;
                    """, (kind, allowed, reason)
                )
                conn.commit()
                logger.info(f"Kind {kind} has been updated with allowed={allowed} and reason='{reason}'")
                return True
        except psycopg.Error as e:
            logger.error(f"Error updating allowed kind: {e}")
            return False
        
    async def query_kind_list(self, conn, cur, kind, logger):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT kind, allowed, reason
                    FROM allowed_kinds
                    WHERE kind = %s;
                    """, (kind,)
                )
                result = cur.fetchone()
                if result:
                    kind_value, allowed, reason = result
                    logger.info(f"Found kind {kind_value} with allowed={allowed} and reason='{reason}'")
                    return {
                        "kind": kind_value,
                        "allowed": allowed,
                        "reason": reason
                    }
                else:
                    logger.info(f"No record found for kind {kind}")
                    return None
        except psycopg.Error as e:
            logger.error(f"Error querying allowed kind: {e}")
            return None
        
    async def insert_pubkey_list(self, conn, cur, pubkey, allowed, reason, logger):
        try:
            await cur.execute(
                """
                INSERT INTO allowed_pubkeys (pubkey, allowed, reason)
                VALUES (%s, %s, %s)
                ON CONFLICT (pubkey) DO UPDATE 
                SET allowed = EXCLUDED.allowed, 
                    reason = EXCLUDED.reason;
                """, (pubkey, allowed, reason)
            )
            await conn.commit()
            logger.info(f"Pubkey {pubkey} has been updated with allowed={allowed} and reason='{reason}'")
            return True  # Return some meaningful result
        except psycopg.Error as e:
            logger.error(f"Error updating allowed pubkey: {e}")
            return False  # Return failure result
        
    async def query_pubkey_list(conn, cur, pubkey, logger):
        try:
            await cur.execute(
                """
                SELECT pubkey, allowed, reason
                FROM allowed_pubkeys
                WHERE pubkey = %s;
                """, (pubkey,)
            )
            result = await cur.fetchone()
            if result:
                pubkey_value, allowed, reason = result
                logger.info(f"Found pubkey {pubkey_value} with allowed={allowed} and reason='{reason}'")
                return {
                    "pubkey": pubkey_value,
                    "allowed": allowed,
                    "reason": reason
                }
            else:
                logger.info(f"No record found for pubkey {pubkey}")
                return None
        except psycopg.Error as e:
            logger.error(f"Error querying allowed pubkey: {e}")
            return None
        
    async def insert_ip_list(conn, cur, ip_address, allowed, reason, logger):
        try:
            await cur.execute(
                """
                INSERT INTO allowed_ips (ip_address, allowed, reason)
                VALUES (%s, %s, %s)
                ON CONFLICT (ip_address) DO UPDATE 
                SET allowed = EXCLUDED.allowed, 
                    reason = EXCLUDED.reason;
                """, (ip_address, allowed, reason)
            )
            await conn.commit()
            logger.info(f"IP address {ip_address} has been updated with allowed={allowed} and reason='{reason}'")
            return True  # Return success result
        except psycopg.Error as e:
            logger.error(f"Error updating allowed IP address: {e}")
            return False  # Return failure result
    
    async def query_ip_list(conn, cur, ip_address, logger):
        try:
            await cur.execute(
                """
                SELECT ip_address, allowed, reason
                FROM allowed_ips
                WHERE ip_address = %s;
                """, (ip_address,)
            )
            result = await cur.fetchone()
            if result:
                ip_value, allowed, reason = result
                logger.info(f"Found IP address {ip_value} with allowed={allowed} and reason='{reason}'")
                return {
                    "ip_address": ip_value,
                    "allowed": allowed,
                    "reason": reason
                }
            else:
                logger.info(f"No record found for IP address {ip_address}")
                return None
        except psycopg.Error as e:
            logger.error(f"Error querying allowed IP address: {e}")
            return None




