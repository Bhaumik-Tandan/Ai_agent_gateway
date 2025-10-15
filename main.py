import os
import uvicorn
from aegis.gateway import create_app


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    policy_dir = os.getenv("POLICY_DIR", "./policies")
    otel_endpoint = os.getenv("OTEL_ENDPOINT", "")
    
    app = create_app(
        policy_dir=policy_dir,
        otel_endpoint=otel_endpoint if otel_endpoint else None
    )
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

