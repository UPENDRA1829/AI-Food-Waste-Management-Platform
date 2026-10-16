
def get_authenticated_business_id(
    x_api_key: str | None = Header(default=None, alias="X-API-Key")
) -> int:
    """Validate a business API key and return its business ID."""

    if x_api_key is None or not x_api_key.strip():
        raise HTTPException(
            status_code=401,
            detail="Missing API key"
        )

    key_hash = hashlib.sha256(
        x_api_key.encode("utf-8")
    ).hexdigest()

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT business_id
            FROM business_api_keys
            WHERE key_hash = ?
              AND is_active = 1
        """, (key_hash,))

        result = cursor.fetchone()

        if result is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid or inactive API key"
            )

        return result["business_id"]

    finally:
        connection.close()
