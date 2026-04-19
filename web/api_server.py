"""
Web API Server
--------------
Flask-based REST API that serves the web player and exposes
station state for external consumers (web UI, Discord bot, etc.)

Endpoints:
  GET  /now_playing      -> current track + station state
    GET  /queue            -> upcoming tracks (array)
      POST /request          -> submit a track request
        GET  /health           -> system health check
          GET  /                 -> serve the web player HTML
          """

          from __future__ import annotations

          import json
          import logging
          import os
          from dataclasses import asdict
          from pathlib import Path

          from flask import Flask, jsonify, request, send_file, abort
          from flask_cors import CORS

          from orchestration.state_manager import get_state_manager
          from services.playlist_engine import get_engine, Track

          logger = logging.getLogger(__name__)

          app = Flask(__name__, static_folder="player", static_url_path="")
          CORS(app)  # Allow web player on different origin

          PLAYER_HTML = Path(__file__).parent / "player" / "index.html"


          # ── ROUTES ────────────────────────────────────────────────────────────────────

          @app.get("/")
          def index():
              if PLAYER_HTML.exists():
                      return send_file(PLAYER_HTML)
                          return "<h1>Radio Free Gonzo</h1><p>Web player not found. Check web/player/index.html</p>"


                          @app.get("/now_playing")
                          def now_playing():
                              sm   = get_state_manager()
                                  data = {
                                          "now_playing":   sm.now_playing,
                                                  "is_streaming":  sm.is_streaming,
                                                          "tracks_played": sm.tracks_played_count,
                                                                  "segment_type":  getattr(sm._state, "current_segment_type", "music"),
                                                                      }
                                                                          return jsonify(data)


                                                                          @app.get("/queue")
                                                                          def queue():
                                                                              engine = get_engine()
                                                                                  return jsonify([asdict(t) for t in engine.state.queue])


                                                                                  @app.post("/request")
                                                                                  def request_track():
                                                                                      body = request.get_json(silent=True) or {}
                                                                                          artist = (body.get("artist") or "").strip()
                                                                                              title  = (body.get("title")  or "").strip()
                                                                                                  req_by = (body.get("requested_by") or "web").strip()

                                                                                                      if not artist:
                                                                                                              return jsonify({"error": "artist is required"}), 400
                                                                                                              
                                                                                                                  engine = get_engine()
                                                                                                                      track  = Track(
                                                                                                                              title=title or "[Requested]",
                                                                                                                                      artist=artist,
                                                                                                                                              youtube_query=f"{artist} {title} official audio".strip(),
                                                                                                                                                      requested_by=req_by,
                                                                                                                                                          )
                                                                                                                                                              engine.inject_request(track, position=1)
                                                                                                                                                              
                                                                                                                                                                  logger.info("Web request: %s - %s by %s", artist, title, req_by)
                                                                                                                                                                      return jsonify({"status": "queued", "artist": artist, "title": title}), 201
                                                                                                                                                                      
                                                                                                                                                                      
                                                                                                                                                                      @app.get("/health")
                                                                                                                                                                      def health():
                                                                                                                                                                          sm     = get_state_manager()
                                                                                                                                                                              engine = get_engine()
                                                                                                                                                                                  return jsonify({
                                                                                                                                                                                          "status":        "ok",
                                                                                                                                                                                                  "is_streaming":  sm.is_streaming,
                                                                                                                                                                                                          "queue_length":  len(engine.state.queue),
                                                                                                                                                                                                                  "tracks_played": sm.tracks_played_count,
                                                                                                                                                                                                                      })
                                                                                                                                                                                                                      
                                                                                                                                                                                                                      
                                                                                                                                                                                                                      @app.errorhandler(404)
                                                                                                                                                                                                                      def not_found(e):
                                                                                                                                                                                                                          return jsonify({"error": "not found"}), 404
                                                                                                                                                                                                                          
                                                                                                                                                                                                                          
                                                                                                                                                                                                                          @app.errorhandler(500)
                                                                                                                                                                                                                          def server_error(e):
                                                                                                                                                                                                                              return jsonify({"error": "internal server error"}), 500
                                                                                                                                                                                                                              
                                                                                                                                                                                                                              
                                                                                                                                                                                                                              # ── ENTRY POINT ───────────────────────────────────────────────────────────────
                                                                                                                                                                                                                              
                                                                                                                                                                                                                              def run_server(host="0.0.0.0", port=8080, debug=False):
                                                                                                                                                                                                                                  logger.info("API server starting on %s:%s", host, port)
                                                                                                                                                                                                                                      app.run(host=host, port=port, debug=debug, use_reloader=False)
                                                                                                                                                                                                                                      
                                                                                                                                                                                                                                      
                                                                                                                                                                                                                                      if __name__ == "__main__":
                                                                                                                                                                                                                                          logging.basicConfig(level=logging.INFO)
                                                                                                                                                                                                                                              run_server(
                                                                                                                                                                                                                                                      host=os.getenv("API_HOST", "0.0.0.0"),
                                                                                                                                                                                                                                                              port=int(os.getenv("API_PORT", "8080")),
                                                                                                                                                                                                                                                                  )
                                                                                                                                                                                                                                                                  
