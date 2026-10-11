use serde_json::Value;
use std::time::{Duration, Instant};

pub const TABS: [&str; 5] = ["General", "Model", "Advanced", "Environment", "About"];

pub fn callback_budget(deadline: Instant, now: Instant) -> Result<Duration, String> {
    deadline
        .checked_duration_since(now)
        .filter(|remaining| !remaining.is_zero())
        .map(|remaining| remaining.min(Duration::from_secs(2)))
        .ok_or_else(|| "Probe deadline expired".into())
}

pub fn validate(
    sample: &Value,
    tab: &str,
    namespace: &str,
    version: &str,
    data: &str,
) -> Result<(), String> {
    let require =
        |condition: bool, message: &str| condition.then_some(()).ok_or_else(|| message.to_string());
    let page = sample["url"]
        .as_str()
        .and_then(|value| url::Url::parse(value).ok());
    require(
        page.is_some_and(|page| {
            matches!(page.scheme(), "http" | "https")
                && page.host_str() == Some("tauri.localhost")
                && page.port().is_none()
                && page.username().is_empty()
                && page.password().is_none()
                && page.path() == "/index.html"
                && page.query() == Some("view=settings")
        }),
        "Not the embedded Settings page",
    )?;
    require(sample["readyState"] == "complete", "Page load incomplete")?;
    require(sample["activeTab"] == tab, "Requested tab not selected")?;
    require(
        sample["tabs"] == serde_json::json!(TABS),
        "Five tab navigation missing",
    )?;
    for field in ["positiveRects", "marker", "markerRect", "cssLoaded"] {
        require(
            sample[field] == true,
            &format!("Missing render evidence: {field}"),
        )?;
    }
    require(sample["probeError"].is_null(), "DOM measurement failed")?;
    for field in ["errors", "alerts"] {
        require(
            sample[field]
                .as_array()
                .is_some_and(|values| values.is_empty()),
            &format!("Page reported {field}"),
        )?;
    }
    if tab == "General" {
        require(
            sample["namespace"] == namespace && sample["versionPlaceholder"] == version,
            "Actual get_settings/snapshot response not rendered",
        )?;
        require(
            sample["tokenPlaceholder"] == "Optional token"
                && sample["offline"] == true
                && sample["startOnLogin"] == false,
            "Isolated settings not rendered",
        )?;
    }
    if tab == "Model" {
        require(
            sample["manageModelsDisabled"] == true,
            "Stopped snapshot not reflected in Model controls",
        )?;
    }
    if tab == "About" {
        require(sample["footer"] == false, "About unexpectedly offers Save")?;
        require(
            sample["aboutVersion"] == version
                && sample["aboutData"] == data
                && sample["imageLoaded"] == true,
            "About snapshot/embedded asset not rendered",
        )?;
    } else {
        for field in ["footer", "footerInViewport", "saveDisabled"] {
            require(
                sample[field] == true,
                &format!("Invalid unchanged footer: {field}"),
            )?;
        }
        require(
            sample["footerText"]
                .as_str()
                .is_some_and(|text| text.contains("next backend launch")),
            "Footer does not describe stopped backend",
        )?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn ready(tab: &str) -> Value {
        json!({
            "url": "http://tauri.localhost/index.html?view=settings",
            "readyState": "complete", "activeTab": tab,
            "tabs": TABS, "positiveRects": true, "markerRect": true, "cssLoaded": true,
            "errors": [], "alerts": [], "probeError": null,
            "namespace": "probe-unique", "versionPlaceholder": "0.3.70",
            "tokenPlaceholder": "Optional token", "offline": true,
            "startOnLogin": false, "marker": true,
            "footer": tab != "About", "footerInViewport": true,
            "saveDisabled": true,
            "footerText": "Changes apply on the next backend launch.",
            "aboutVersion": "0.3.70", "aboutData": "probe/data",
            "imageLoaded": true, "manageModelsDisabled": true
        })
    }

    fn accepts(sample: &Value, tab: &str) -> bool {
        validate(sample, tab, "probe-unique", "0.3.70", "probe/data").is_ok()
    }

    #[test]
    fn each_loaded_tab_can_pass_without_mutating_settings() {
        for tab in TABS {
            assert!(accepts(&ready(tab), tab), "{tab}");
        }
    }

    #[test]
    fn completed_load_or_ipc_requests_do_not_accept_blank_dom() {
        let mut sample = ready("General");
        sample["positiveRects"] = json!(false);
        assert!(!accepts(&sample, "General"));
        sample = ready("General");
        sample["cssLoaded"] = json!(false);
        assert!(!accepts(&sample, "General"));
        sample = ready("General");
        sample["namespace"] = json!("");
        sample["versionPlaceholder"] = json!("Release version");
        assert!(!accepts(&sample, "General"));
    }

    #[test]
    fn selection_without_rendered_content_is_rejected() {
        let mut sample = ready("Advanced");
        sample["markerRect"] = json!(false);
        assert!(!accepts(&sample, "Advanced"));
        sample = ready("Model");
        assert!(!accepts(&sample, "Environment"));
        sample["tabs"] = json!(["General", "Model"]);
        assert!(!accepts(&sample, "Model"));
    }

    #[test]
    fn broken_footer_or_about_asset_is_rejected() {
        for field in ["saveDisabled", "footerInViewport", "footer"] {
            let mut sample = ready("Environment");
            sample[field] = json!(false);
            assert!(!accepts(&sample, "Environment"), "{field}");
        }
        let mut sample = ready("About");
        sample["imageLoaded"] = json!(false);
        assert!(!accepts(&sample, "About"));
        sample = ready("About");
        sample["footer"] = json!(true);
        assert!(!accepts(&sample, "About"));
    }

    #[test]
    fn script_errors_alerts_and_foreign_pages_are_rejected() {
        let mut sample = ready("General");
        sample["errors"] = json!(["IPC unavailable"]);
        assert!(!accepts(&sample, "General"));
        sample = ready("General");
        sample["alerts"] = json!(["Command unavailable to this window"]);
        assert!(!accepts(&sample, "General"));
        sample = ready("General");
        sample["url"] = json!("http://127.0.0.1:1420/?view=settings");
        assert!(!accepts(&sample, "General"));
    }

    #[test]
    fn late_callbacks_cannot_reset_or_extend_the_total_deadline() {
        let started = Instant::now();
        let deadline = started + Duration::from_secs(30);
        assert_eq!(
            callback_budget(deadline, started).unwrap(),
            Duration::from_secs(2)
        );
        assert_eq!(
            callback_budget(deadline, deadline - Duration::from_millis(20)).unwrap(),
            Duration::from_millis(20)
        );
        assert!(callback_budget(deadline, deadline).is_err());
        assert!(callback_budget(deadline, deadline + Duration::from_millis(1)).is_err());
    }
}
