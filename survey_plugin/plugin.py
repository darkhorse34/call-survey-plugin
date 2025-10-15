from .api import bp as blueprint

class Plugin:
    def load(self, app_or_deps):
        app = app_or_deps.get("app") if isinstance(app_or_deps, dict) else app_or_deps
        app.register_blueprint(blueprint, url_prefix="/api/calld/1.0")
        # expose config to dialplan via env var, picked up by survey.conf
        cfg = app.config.get("wazo_survey", {}) or {}
        webhook = cfg.get("webhook_url") or ""
        # ensure CHANNEL_VARS exists and add survey-related vars for dialplan
        app.config["CHANNEL_VARS"] = app.config.get("CHANNEL_VARS", {})
        if webhook:
            app.config["CHANNEL_VARS"]["WAZO_SURVEY_WEBHOOK"] = webhook
        # dialplan plumbing: context/exten/timeout exported as channel vars
        app.config["CHANNEL_VARS"]["WAZO_SURVEY_CONTEXT"] = cfg.get("survey_context", "xivo-extrafeatures")
        app.config["CHANNEL_VARS"]["WAZO_SURVEY_EXTEN"] = cfg.get("survey_exten", "8899")
        # store as string because channel vars are textual
        app.config["CHANNEL_VARS"]["WAZO_SURVEY_TIMEOUT"] = str(cfg.get("survey_timeout", 15))
        # optional webhook secret (kept out of GET /config responses)
        secret = cfg.get("webhook_secret")
        if secret:
            app.config["CHANNEL_VARS"]["WAZO_SURVEY_WEBHOOK_SECRET"] = secret

    def unload(self, app_or_deps):
        pass
