const { useEffect, useMemo, useState } = React;
const h = React.createElement;

const CITIES = ["Ahmedabad", "Bengaluru", "Chennai", "Delhi", "Hyderabad", "Kolkata", "Mumbai", "Pune"];
const TYPES = ["Apartment", "Villa", "Independent House"];
const FURNISHING = ["Unfurnished", "Semi-furnished", "Furnished"];
const indian = (value) => new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR", maximumFractionDigits: 0,
}).format(Number(value) || 0);

function HomeValueApp() {
  const [page, setPage] = useState("home");
  const [user, setUser] = useState(null);
  const [csrf, setCsrf] = useState("");
  const [properties, setProperties] = useState([]);
  const [saved, setSaved] = useState([]);
  const [activity, setActivity] = useState({ predictions: [], prediction_count: 0, saved_count: 0 });
  const [metrics, setMetrics] = useState(null);
  const [filters, setFilters] = useState({ city: "", property_type: "", q: "", min_price: "", max_price: "" });
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(null);
  const [estimate, setEstimate] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authReturnPage, setAuthReturnPage] = useState("dashboard");
  const [showPassword, setShowPassword] = useState(false);

  const api = async (path, options = {}) => {
    const response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.method && options.method !== "GET" && csrf ? { "X-CSRFToken": csrf } : {}),
        ...options.headers,
      },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  };

  const notify = (message) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3200);
  };

  const loadProperties = async (filterValues = filters) => {
    const query = new URLSearchParams(Object.entries(filterValues).filter(([, value]) => value));
    const data = await api(`/api/properties?${query}`);
    setProperties(data.properties);
  };

  const loadUserData = async () => {
    if (!user) {
      setSaved([]);
      return;
    }
    const [savedData, activityData] = await Promise.all([
      api("/api/saved"), api("/api/dashboard"),
    ]);
    setSaved(savedData.properties);
    setActivity(activityData);
  };

  useEffect(() => {
    api("/api/session").then((data) => {
      setUser(data.user);
      setCsrf(data.csrf_token);
      return api("/api/properties");
    }).then((data) => setProperties(data.properties))
      .catch((cause) => setError(cause.message));
  }, []);

  useEffect(() => {
    if (user) loadUserData().catch((cause) => setError(cause.message));
  }, [user]);

  const navigate = (next, filterValues = filters) => {
    setPage(next);
    setError("");
    setEstimate(null);
    setSelected(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (next === "home" || next === "explore") {
      loadProperties(filterValues).catch((cause) => setError(cause.message));
    }
    if (next === "performance" && !metrics) {
      api("/api/model-performance").then(setMetrics).catch((cause) => setError(cause.message));
    }
  };

  const openManualEntry = () => {
    if (user) {
      navigate("predict");
      return;
    }
    setAuthMode("login");
    setAuthReturnPage("predict");
    navigate("auth");
  };

  const submitAuth = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const payload = Object.fromEntries(form.entries());
    try {
      const endpoint = authMode === "register" ? "/api/auth/register" : "/api/auth/login";
      const data = await api(endpoint, { method: "POST", body: JSON.stringify(payload) });
      setCsrf(data.csrf_token);
      setUser(data.user);
      setPage(authReturnPage);
      event.currentTarget.reset();
      notify(`Welcome${authMode === "register" ? " to HomeValue" : " back"}, ${data.user.name.split(" ")[0]}.`);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    try {
      const data = await api("/api/auth/logout", { method: "POST", body: "{}" });
      setCsrf(data.csrf_token);
      setUser(null);
      setPage("home");
      notify("You have been signed out.");
    } catch (cause) {
      setError(cause.message);
    }
  };

  const toggleSave = async (property) => {
    if (!user) {
      setAuthMode("login");
      setPage("auth");
      setError("Log in to save properties to your account.");
      return;
    }
    const isSaved = saved.some((item) => item.id === property.id);
    try {
      await api(`/api/saved/${property.id}`, { method: isSaved ? "DELETE" : "POST", body: "{}" });
      await loadUserData();
      await loadProperties();
      notify(isSaved ? "Property removed from your saved list." : "Property saved to your favourites.");
    } catch (cause) {
      setError(cause.message);
    }
  };

  const submitPrediction = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    for (const field of ["area_sqft", "bedrooms", "bathrooms", "property_age"]) values[field] = Number(values[field]);
    try {
      const result = await api("/api/predict", { method: "POST", body: JSON.stringify(values) });
      setEstimate({ ...result, details: values });
      await loadUserData();
    } catch (cause) {
      setError(cause.message);
    } finally {
      setBusy(false);
    }
  };

  const filteredProperties = useMemo(() => properties, [properties]);
  const savedSet = useMemo(() => new Set(saved.map((item) => item.id)), [saved]);

  const nav = h("header", { className: "hv-header" },
    h("nav", { className: "hv-nav shell" },
      h("a", { className: "hv-brand", href: "#", onClick: (e) => { e.preventDefault(); navigate("home"); } },
        h("span", { className: "hv-brand-mark" }, "H"), h("span", null, "home", h("b", null, "value"))),
      h("div", { className: "hv-nav-links" },
        [["Home", "home"], ["Explore", "explore"], ["Add details", "predict"], ["About", "about"]].map(([label, destination]) =>
        h("button", { key: destination, className: page === destination ? "active" : "", onClick: destination === "predict" ? openManualEntry : () => navigate(destination) }, label))),
      h("div", { className: "hv-nav-actions" },
        user ? h(React.Fragment, null,
          h("button", { className: "hv-nav-user", onClick: () => navigate("dashboard") }, user.name.split(" ")[0]),
          h("button", { className: "hv-button hv-outline hv-small", onClick: logout }, "Log out"))
          : h(React.Fragment, null,
            h("button", { className: "hv-nav-user", onClick: () => { setAuthMode("login"); navigate("auth"); } }, "Log in"),
            h("button", { className: "hv-button hv-primary hv-small", onClick: () => { setAuthMode("register"); navigate("auth"); } }, "Get started")))));

  const propertyCard = (property) => h("article", { className: "hv-property-card", key: property.id },
    h("button", { className: "hv-property-photo", onClick: () => setSelected(property), "aria-label": `View ${property.name}` },
      h("img", { src: property.image_url, alt: property.name, loading: "lazy" }),
      property.is_demo ? h("span", { className: "hv-demo-tag" }, "Demo listing") : null),
    h("div", { className: "hv-property-body" },
      h("strong", { className: "hv-property-price" }, indian(property.price)),
      h("h3", null, property.name),
      h("p", { className: "hv-muted" }, "⌖ ", property.location, ", ", property.city),
      h("div", { className: "hv-property-specs" }, `${Number(property.area_sqft).toLocaleString("en-IN")} sqft  ·  ${property.bedrooms} beds  ·  ${property.bathrooms} baths`),
      h("div", { className: "hv-card-footer" }, h("span", { className: "hv-type" }, property.property_type),
        h("button", { className: "hv-save", onClick: () => toggleSave(property) }, savedSet.has(property.id) ? "♥ Saved" : "♡ Save"))));

  const homePage = h(React.Fragment, null,
    h("section", { className: "hv-hero" }, h("div", { className: "shell hv-hero-content" },
      h("span", { className: "hv-eyebrow" }, "A smarter way to find home"),
      h("h1", null, "Find your dream home with ", h("em", null, "intelligent"), " price prediction."),
      h("p", null, "Explore homes that fit your life, and get a data-informed estimate before you make your move."),
      h("div", { className: "hv-actions" },
        h("button", { className: "hv-button hv-primary", onClick: () => navigate("explore") }, "Explore properties →"),
        h("button", { className: "hv-button hv-glass", onClick: openManualEntry }, "＋ Add house details manually")))),
    h("section", { className: "shell hv-search" },
      h("form", { className: "hv-search-box", onSubmit: (e) => { e.preventDefault(); const data = Object.fromEntries(new FormData(e.currentTarget).entries()); const nextFilters = { ...filters, ...data }; setFilters(nextFilters); navigate("explore", nextFilters); } },
        h("label", null, "City", h("select", { name: "city", defaultValue: "" }, h("option", { value: "" }, "All cities"), CITIES.map((city) => h("option", { key: city }, city)))),
        h("label", null, "Property type", h("select", { name: "property_type", defaultValue: "" }, h("option", { value: "" }, "Any type"), TYPES.map((type) => h("option", { key: type }, type)))),
        h("button", { className: "hv-button hv-primary", type: "submit" }, "⌕ Search homes"))),
    h("section", { className: "shell hv-section" },
      h("div", { className: "hv-section-head" }, h("div", null, h("span", { className: "hv-eyebrow" }, "A place to begin"), h("h2", null, "Featured homes"), h("p", { className: "hv-muted" }, "Explore a few example listings to get inspired.")), h("button", { className: "hv-link", onClick: () => navigate("explore") }, "See all properties →")),
      h("div", { className: "hv-grid" }, filteredProperties.slice(0, 3).map(propertyCard)),
      h("p", { className: "hv-disclosure" }, "Listings shown are sample demo data for this academic project.")),
    h("section", { className: "hv-how" }, h("div", { className: "shell" }, h("h2", null, "From curious to confident"),
      h("div", { className: "hv-how-grid" }, [["01", "Explore what fits", "Filter sample homes by city, type, budget and size."], ["02", "Share the details", "Tell our trained model about the property you're considering."], ["03", "Get an estimate", "See a model-generated estimate in your private history."]].map((item) => h("article", { className: "hv-how-card", key: item[0] }, h("span", null, item[0]), h("h3", null, item[1]), h("p", null, item[2])))))),
    h("section", { className: "shell hv-about-band" }, h("div", null, h("span", { className: "hv-eyebrow" }, "A machine-learning project"), h("h2", null, "Real estate meets machine learning."), h("p", null, "Four regression models are trained and compared on a clearly disclosed synthetic housing dataset. Predictions are estimates, not market valuations."), h("button", { className: "hv-button hv-light", onClick: () => navigate("performance") }, "Explore model insights →"))));

  const explorePage = h("section", { className: "shell hv-explore" },
    h("div", { className: "hv-page-heading" }, h("span", { className: "hv-eyebrow" }, "Explore homes"), h("h1", null, "Find a place that feels like yours."), h("p", { className: "hv-muted" }, "Filter the sample listings and save the ones you love.")),
    h("form", { className: "hv-filter-bar", onSubmit: async (e) => { e.preventDefault(); const values = Object.fromEntries(new FormData(e.currentTarget).entries()); setFilters(values); try { await loadProperties(values); } catch (cause) { setError(cause.message); } } },
      h("input", { name: "q", placeholder: "Search a home or location", defaultValue: filters.q }),
      h("select", { name: "city", defaultValue: filters.city }, h("option", { value: "" }, "All cities"), CITIES.map((city) => h("option", { key: city }, city))),
      h("select", { name: "property_type", defaultValue: filters.property_type }, h("option", { value: "" }, "Any property type"), TYPES.map((type) => h("option", { key: type }, type))),
      h("input", { type: "number", min: "0", name: "min_price", placeholder: "Min price ₹", defaultValue: filters.min_price }),
      h("input", { type: "number", min: "0", name: "max_price", placeholder: "Max price ₹", defaultValue: filters.max_price }),
      h("button", { className: "hv-button hv-primary", type: "submit" }, "Apply filters"),
      h("button", { className: "hv-button hv-outline", type: "button", onClick: () => { const clean = { city: "", property_type: "", q: "", min_price: "", max_price: "" }; setFilters(clean); loadProperties(clean).catch((cause) => setError(cause.message)); } }, "Clear")),
    h("div", { className: "hv-result-count" }, `${properties.length} demo listing${properties.length === 1 ? "" : "s"} found`),
    properties.length ? h("div", { className: "hv-grid" }, properties.map(propertyCard)) : h("div", { className: "hv-empty" }, "No homes match these filters. Try broadening your search."));

  const authPage = h("section", { className: "hv-auth shell" },
    h("div", { className: "hv-auth-art" },
      h("span", { className: "hv-eyebrow" }, "Home search, thoughtfully simplified"),
      h("h1", null, "Big decisions feel better with a little more clarity."),
      h("p", null, "Save homes, add your property details, and keep every estimate in one place."),
      h("div", { className: "hv-auth-benefits" },
        h("span", null, h("i", null, "✓"), "Private prediction history"),
        h("span", null, h("i", null, "✓"), "Your own saved-home shortlist"),
        h("span", null, h("i", null, "✓"), "Machine-learning price estimates")),
      h("div", { className: "hv-auth-art-note" }, "Your next chapter starts at home.")),
    h("form", { className: "hv-auth-form", onSubmit: submitAuth },
      h("span", { className: "hv-eyebrow" }, authMode === "login" ? "Welcome back" : "Your next chapter"),
      h("h2", null, authMode === "login" ? "Sign in to HomeValue" : "Create your account"),
      h("p", { className: "hv-auth-subtitle" }, authMode === "login" ? "Pick up where you left off." : "Create an account to save homes and estimates."),
      h("div", { className: "hv-auth-tabs" },
        h("button", { type: "button", className: authMode === "login" ? "active" : "", onClick: () => { setAuthMode("login"); setError(""); } }, "Log in"),
        h("button", { type: "button", className: authMode === "register" ? "active" : "", onClick: () => { setAuthMode("register"); setError(""); } }, "Create account")),
      authMode === "register" ? h("label", null, "Full name", h("input", { name: "name", minLength: 2, maxLength: 80, required: true, autoComplete: "name", placeholder: "Your name" })) : null,
      h("label", null, "Email address", h("input", { name: "email", type: "email", maxLength: 254, required: true, autoComplete: "email", placeholder: "you@example.com" })),
      h("label", { className: "hv-password-label" }, "Password",
        h("span", { className: "hv-password-control" },
          h("input", { name: "password", type: showPassword ? "text" : "password", minLength: authMode === "register" ? 8 : undefined, required: true, autoComplete: authMode === "register" ? "new-password" : "current-password", placeholder: authMode === "register" ? "At least 8 characters" : "Enter your password" }),
          h("button", { type: "button", onClick: () => setShowPassword(!showPassword), "aria-label": showPassword ? "Hide password" : "Show password" }, showPassword ? "Hide" : "Show"))),
      authMode === "register" ? h("label", null, "Confirm password", h("input", { name: "confirm_password", type: showPassword ? "text" : "password", minLength: 8, required: true, autoComplete: "new-password", placeholder: "Re-enter your password" })) : null,
      h("button", { className: "hv-button hv-primary hv-full hv-auth-submit", type: "submit", disabled: busy }, busy ? "Please wait…" : authMode === "login" ? "Log in securely  →" : "Create account  →"),
      h("p", { className: "hv-auth-terms" }, "Your account details are protected. Passwords are securely hashed."),
      h("button", { type: "button", className: "hv-auth-back", onClick: () => navigate("home") }, "← Back to HomeValue")));

  const predictPage = estimate ? h("section", { className: "shell hv-prediction" },
    h("div", { className: "hv-estimate-success" }, h("span", { className: "hv-eyebrow" }, "Your estimate is ready"), h("h1", null, "A helpful starting point for your search."), h("p", null, `Generated by ${estimate.model_name}.`)),
    h("div", { className: "hv-estimate-card" }, h("span", null, "Estimated house price"), h("strong", null, indian(estimate.predicted_price)), h("p", null, `${indian(estimate.price_per_sqft)} per sq ft`),
      h("hr"), h("h3", null, "Property details"), h("p", null, `${estimate.details.location}, ${estimate.details.city} · ${estimate.details.property_type}`),
      h("p", null, `${Number(estimate.details.area_sqft).toLocaleString("en-IN")} sq ft · ${estimate.details.bedrooms} beds · ${estimate.details.bathrooms} baths · ${estimate.details.property_age} years old`),
      h("div", { className: "hv-disclaimer-box" }, "Approximate estimate based on synthetic demonstration data. This is not a guaranteed market price or professional appraisal."),
      h("button", { className: "hv-button hv-primary", onClick: () => setEstimate(null) }, "Make another prediction")))
    : h("section", { className: "shell hv-prediction" },
      h("div", { className: "hv-page-heading" }, h("span", { className: "hv-eyebrow" }, "Manual property entry · Private estimate"), h("h1", null, "Add your house details."), h("p", { className: "hv-muted" }, "Enter the property's information below to get a model-generated price estimate. Your prediction is saved privately to your account.")),
      h("form", { className: "hv-predict-form", onSubmit: submitPrediction },
        h("label", null, "City", h("select", { name: "city", required: true }, h("option", { value: "" }, "Choose a city"), CITIES.map((city) => h("option", { key: city }, city)))),
        h("label", null, "Location", h("input", { name: "location", required: true, maxLength: 80, placeholder: "e.g. Whitefield" })),
        h("label", null, "Property type", h("select", { name: "property_type", required: true }, h("option", { value: "" }, "Choose a type"), TYPES.map((type) => h("option", { key: type }, type)))),
        h("label", null, "Area (sq ft)", h("input", { name: "area_sqft", type: "number", min: 200, max: 20000, required: true, placeholder: "1450" })),
        h("label", null, "Bedrooms", h("input", { name: "bedrooms", type: "number", min: 1, max: 12, required: true, placeholder: "3" })),
        h("label", null, "Bathrooms", h("input", { name: "bathrooms", type: "number", min: 1, max: 12, required: true, placeholder: "2" })),
        h("label", null, "Property age (years)", h("input", { name: "property_age", type: "number", min: 0, max: 150, required: true, placeholder: "5" })),
        h("label", null, "Parking", h("select", { name: "parking", required: true }, h("option", { value: "" }, "Choose"), h("option", null, "Yes"), h("option", null, "No"))),
        h("label", null, "Furnishing", h("select", { name: "furnishing", required: true }, h("option", { value: "" }, "Choose"), FURNISHING.map((value) => h("option", { key: value }, value)))),
        h("button", { className: "hv-button hv-primary hv-full hv-form-submit", type: "submit", disabled: busy }, busy ? "Training estimate…" : "Predict house price →"),
        h("p", { className: "hv-disclosure hv-form-disclosure" }, "Synthetic academic demonstration data only. Estimates are approximate.")));

  const dashboardPage = h("section", { className: "shell hv-dashboard" },
    h("div", { className: "hv-page-heading" }, h("span", { className: "hv-eyebrow" }, "Your HomeValue space"), h("h1", null, `Welcome home, ${user?.name.split(" ")[0] || ""}.`), h("p", { className: "hv-muted" }, "Your home search, all in one place.")),
    h("div", { className: "hv-stats" }, [["Predictions", activity.prediction_count, "↗"], ["Saved properties", activity.saved_count, "♡"]].map((item) => h("article", { className: "hv-stat", key: item[0] }, h("span", null, item[2]), h("small", null, item[0]), h("strong", null, item[1]))),
      h("button", { className: "hv-stat hv-stat-action", onClick: () => navigate("explore") }, h("span", null, "⌂"), h("small", null, "Looking for a home?"), h("strong", null, "Explore listings →"))),
    h("div", { className: "hv-section-head hv-history-head" }, h("div", null, h("span", { className: "hv-eyebrow" }, "Your activity"), h("h2", null, "Recent predictions")), h("button", { className: "hv-link", onClick: async () => { try { const data = await api("/api/history"); setActivity({ ...activity, predictions: data.predictions }); navigate("history"); } catch (cause) { setError(cause.message); } } }, "View history →")),
    activity.predictions.length ? h("div", { className: "hv-history-table" }, activity.predictions.map((item) => h("div", { className: "hv-history-row", key: item.id }, h("span", null, h("b", null, `${item.location}, ${item.city}`), h("small", null, item.property_type)), h("span", null, `${Number(item.area_sqft).toLocaleString("en-IN")} sqft`), h("b", { className: "hv-property-price" }, indian(item.predicted_price)))))
      : h("div", { className: "hv-empty" }, "Your first estimate is waiting. ", h("button", { className: "hv-link", onClick: () => navigate("predict") }, "Predict a home price →")),
    h("div", { className: "hv-dashboard-actions" }, h("button", { className: "hv-button hv-primary", onClick: openManualEntry }, "＋ Add house details manually"), h("button", { className: "hv-button hv-outline", onClick: () => navigate("saved") }, "♡ Saved homes")));

  const historyPage = h("section", { className: "shell hv-explore" }, h("div", { className: "hv-page-heading" }, h("span", { className: "hv-eyebrow" }, "Your activity"), h("h1", null, "Prediction history")),
    activity.predictions.length ? h("div", { className: "hv-history-table" }, activity.predictions.map((item) => h("div", { className: "hv-history-row", key: item.id }, h("span", null, h("b", null, `${item.location}, ${item.city}`), h("small", null, `${item.property_type} · ${item.created_at.slice(0, 10)}`)), h("span", null, `${Number(item.area_sqft).toLocaleString("en-IN")} sqft · ${item.bedrooms} beds`), h("b", { className: "hv-property-price" }, indian(item.predicted_price)))))
      : h("div", { className: "hv-empty" }, "No prediction history yet. Make your first estimate."));

  const savedPage = h("section", { className: "shell hv-section" }, h("div", { className: "hv-page-heading" }, h("span", { className: "hv-eyebrow" }, "Your shortlist"), h("h1", null, "Saved properties")),
    saved.length ? h("div", { className: "hv-grid" }, saved.map(propertyCard)) : h("div", { className: "hv-empty" }, "Your shortlist is ready to grow. Save homes while you explore."));

  const performancePage = h("section", { className: "shell hv-explore" }, h("div", { className: "hv-page-heading" }, h("span", { className: "hv-eyebrow" }, "Model insights"), h("h1", null, "Model performance, made transparent."), h("p", { className: "hv-muted" }, "Actual metrics calculated from this project's held-out test data.")),
    metrics ? h(React.Fragment, null, h("div", { className: "hv-best-model" }, h("span", null, "Selected model"), h("strong", null, metrics.best_model), h("small", null, `${metrics.dataset_rows.toLocaleString("en-IN")} synthetic training rows · lowest test RMSE`)),
      h("div", { className: "hv-metric-grid" }, Object.entries(metrics.metrics).map(([name, score]) => h("article", { className: "hv-metric", key: name }, h("h3", null, name), h("p", null, `MAE  ${indian(score.mae)}`), h("p", null, `RMSE  ${indian(score.rmse)}`), h("p", null, `R²  ${score.r2.toFixed(4)}`)))),
      h("div", { className: "hv-disclaimer-box" }, metrics.dataset_note, " Scores do not establish prediction accuracy on real-world property prices."))
      : h("p", null, "Loading evaluation…"));

  const aboutPage = h("section", { className: "shell hv-about-page" }, h("span", { className: "hv-eyebrow" }, "About HomeValue"), h("h1", null, "More clarity for a big decision."), h("p", null, "A full-stack academic project exploring how machine learning can support a home search. HomeValue combines property discovery, saved listings, user-specific prediction history and four compared scikit-learn regression models."), h("div", { className: "hv-disclaimer-box" }, "The included dataset is synthetically generated for this academic demonstration. It is not sourced from actual property transactions and should not be used for purchasing or investment decisions."), h("button", { className: "hv-button hv-primary", onClick: () => navigate("performance") }, "View model performance →"));

  const modal = selected && h("div", { className: "hv-modal-backdrop", onClick: () => setSelected(null) }, h("article", { className: "hv-modal", onClick: (e) => e.stopPropagation() },
    h("button", { className: "hv-modal-close", onClick: () => setSelected(null), "aria-label": "Close details" }, "×"),
    h("img", { src: selected.image_url, alt: selected.name }),
    h("span", { className: "hv-eyebrow" }, selected.property_type),
    h("h2", null, selected.name), h("p", { className: "hv-muted" }, `${selected.location}, ${selected.city}`),
    h("strong", { className: "hv-property-price" }, indian(selected.price)),
    h("p", { className: "hv-muted" }, `${Number(selected.area_sqft).toLocaleString("en-IN")} sqft · ${selected.bedrooms} bedrooms · ${selected.bathrooms} bathrooms`),
    h("div", { className: "hv-actions" }, h("button", { className: "hv-button hv-primary", onClick: () => { setSelected(null); openManualEntry(); } }, "Enter my house details"), h("button", { className: "hv-button hv-outline", onClick: () => toggleSave(selected) }, savedSet.has(selected.id) ? "♥ Saved" : "♡ Save home"))));

  const content = page === "home" ? homePage
    : page === "explore" ? explorePage
      : page === "auth" ? authPage
        : page === "predict" ? predictPage
          : page === "dashboard" ? dashboardPage
            : page === "history" ? historyPage
              : page === "saved" ? savedPage
                : page === "performance" ? performancePage
                  : aboutPage;

  return h(React.Fragment, null, nav,
    error && h("div", { className: "shell hv-alert", role: "alert" }, h("span", null, error), h("button", { onClick: () => setError("") }, "×")),
    toast && h("div", { className: "hv-toast", role: "status" }, toast),
    h("main", null, content),
    h("footer", { className: "hv-footer" }, h("div", { className: "shell hv-footer-inner" }, h("a", { className: "hv-brand hv-footer-brand", href: "#", onClick: (e) => { e.preventDefault(); navigate("home"); } }, h("span", { className: "hv-brand-mark" }, "H"), h("span", null, "home", h("b", null, "value"))), h("p", null, "Academic project demonstration · Estimates are approximate, not a market valuation."), h("button", { onClick: () => navigate("performance") }, "Model insights"))),
    modal);
}

ReactDOM.createRoot(document.getElementById("root")).render(React.createElement(HomeValueApp));
