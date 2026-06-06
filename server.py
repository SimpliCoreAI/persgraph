
@app.route("/api/langfuse")
@login_required
def api_langfuse():
    """Proxy to Langfuse API."""  
    try:
        import httpx
        from second_brain.config import settings
        response = httpx.get(f"{settings.LANGFUSE_BASE_URL}/api/metrics", headers={
            "Authorization": f"Bearer {settings.LANGFUSE_SECRET_KEY}"
        })
        response.raise_for_status()  # Raise an error for bad responses
        data = response.json()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
