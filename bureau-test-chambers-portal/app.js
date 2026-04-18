(function () {
	const suitColors = ["#1a2338", "#cfd8ec", "#5d6478", "#14334a"];
	const accentColors = ["#f5bb2a", "#63e2a1", "#ff6e5c", "#9f86ff"];
	const visorColors = ["#f5f8ff", "#79ebff", "#ffd06f", "#ffa6ff"];
	const roleLabels = {
		player: "Player",
		moderator: "▲ Moderator",
		director: "◆ Director"
	};
	const tosStorageKey = "bureau_portal_tos_acceptance_v2026_04_11";
	const urlParams = new URLSearchParams(window.location.search);
	const resetToken = urlParams.get("reset_token") || "";

	const refs = {
		tosOverlay: document.getElementById("tos-overlay"),
		tosCheckbox: document.getElementById("tos-checkbox"),
		tosAcceptButton: document.getElementById("tos-accept-button"),
		tosDeclineButton: document.getElementById("tos-decline-button"),
		tosMessage: document.getElementById("tos-message"),
		portalAddress: document.getElementById("portal-address"),
		portalNote: document.getElementById("portal-note"),
		authPanel: document.getElementById("auth-panel"),
		portalLayout: document.getElementById("portal-layout"),
		connectionState: document.getElementById("connection-state"),
		statusMessage: document.getElementById("status-message"),
		loginUsername: document.getElementById("login-username"),
		loginPassword: document.getElementById("login-password"),
		registerUsername: document.getElementById("register-username"),
		registerPassword: document.getElementById("register-password"),
		registerDisplayName: document.getElementById("register-display-name"),
		registerAcceptTos: document.getElementById("register-accept-tos"),
		resetRequestUsername: document.getElementById("reset-request-username"),
		requestResetButton: document.getElementById("request-reset-button"),
		resetRequestMessage: document.getElementById("reset-request-message"),
		resetRequestPreview: document.getElementById("reset-request-preview"),
		resetRequestLink: document.getElementById("reset-request-link"),
		loginButton: document.getElementById("login-button"),
		registerButton: document.getElementById("register-button"),
		resetPanel: document.getElementById("reset-panel"),
		resetNewPassword: document.getElementById("reset-new-password"),
		resetConfirmPassword: document.getElementById("reset-confirm-password"),
		resetPasswordButton: document.getElementById("reset-password-button"),
		resetPasswordMessage: document.getElementById("reset-password-message"),
		activeUsername: document.getElementById("active-username"),
		displayName: document.getElementById("display-name"),
		suitPreset: document.getElementById("suit-preset"),
		accentPreset: document.getElementById("accent-preset"),
		visorPreset: document.getElementById("visor-preset"),
		saveButton: document.getElementById("save-account"),
		copyJsonButton: document.getElementById("copy-json"),
		logoutButton: document.getElementById("logout-button"),
		currentPassword: document.getElementById("current-password"),
		newPassword: document.getElementById("new-password"),
		confirmNewPassword: document.getElementById("confirm-new-password"),
		changePasswordButton: document.getElementById("change-password-button"),
		passwordMessage: document.getElementById("password-message"),
		jsonPreview: document.getElementById("json-preview"),
		previewHead: document.getElementById("preview-head"),
		previewBodyCore: document.getElementById("preview-body-core"),
		previewChest: document.getElementById("preview-chest"),
		legendSuit: document.getElementById("legend-suit"),
		legendAccent: document.getElementById("legend-accent"),
		legendVisor: document.getElementById("legend-visor"),
		sessionRole: document.getElementById("session-role"),
		banLabel: document.getElementById("ban-label"),
		adminState: document.getElementById("admin-state"),
		moderationUsername: document.getElementById("moderation-username"),
		moderationPassword: document.getElementById("moderation-password"),
		moderationReason: document.getElementById("moderation-reason"),
		moderationMessage: document.getElementById("moderation-message"),
		levelsList: document.getElementById("levels-list"),
		levelsCount: document.getElementById("levels-count"),
		refreshLevelsButton: document.getElementById("refresh-levels-button"),
		buildsList: document.getElementById("builds-list"),
		buildsCount: document.getElementById("builds-count"),
		refreshBuildsButton: document.getElementById("refresh-builds-button"),
		accountList: document.getElementById("account-list"),
		accountCount: document.getElementById("account-count"),
		auditLog: document.getElementById("audit-log"),
		auditCount: document.getElementById("audit-count"),
		auditSearch: document.getElementById("audit-search")
	};

	let currentSession = {
		username: "",
		password: "",
		token: ""
	};
	let currentAccount = null;
	let publishedLevels = [];
	let availableBuilds = [];
	let accountRegistry = [];
	let auditLog = [];

	function clampPreset(value) {
		const parsed = Number.parseInt(value, 10);
		return Number.isFinite(parsed) ? Math.max(0, Math.min(3, parsed)) : 0;
	}

	function normalizeRole(value) {
		if (value === "director" || value === "moderator") {
			return value;
		}
		return "player";
	}

	function normalizeAccount(input) {
		const source = input && typeof input === "object" ? input : {};
		return {
			account_id: String(source.account_id || ""),
			username: String(source.username || ""),
			display_name: String(source.display_name || "Test Subject"),
			suit_preset_index: clampPreset(source.suit_preset_index),
			accent_preset_index: clampPreset(source.accent_preset_index),
			visor_preset_index: clampPreset(source.visor_preset_index),
			role: normalizeRole(source.role),
			banned: Boolean(source.banned)
		};
	}

	function hasAcceptedTos() {
		return localStorage.getItem(tosStorageKey) === "accepted";
	}

	function updateTosVisibility() {
		if (hasAcceptedTos()) {
			refs.tosOverlay.classList.add("hidden");
			if (refs.registerAcceptTos) {
				refs.registerAcceptTos.checked = true;
			}
			return;
		}
		refs.tosOverlay.classList.remove("hidden");
	}

	function setTosMessage(message, mode = "waiting") {
		refs.tosMessage.textContent = message;
		refs.tosMessage.dataset.mode = mode;
	}

	function acceptTos() {
		if (!refs.tosCheckbox.checked) {
			setTosMessage("Check the agreement box before continuing.", "offline");
			return;
		}
		localStorage.setItem(tosStorageKey, "accepted");
		if (refs.registerAcceptTos) {
			refs.registerAcceptTos.checked = true;
		}
		updateTosVisibility();
		setTosMessage("Terms accepted.", "connected");
	}

	function declineTos() {
		localStorage.removeItem(tosStorageKey);
		if (refs.registerAcceptTos) {
			refs.registerAcceptTos.checked = false;
		}
		setTosMessage("The portal stays locked until you accept the Terms of Service.", "offline");
		updateTosVisibility();
	}

	function setStatus(message, mode) {
		refs.statusMessage.textContent = message;
		refs.connectionState.textContent = mode;
		refs.connectionState.dataset.mode = mode.toLowerCase().replace(/\s+/g, "-");
	}

	function setAdminState(message, mode) {
		refs.adminState.textContent = message;
		refs.adminState.dataset.mode = mode.toLowerCase().replace(/\s+/g, "-");
	}

	function setModerationMessage(message, mode = "waiting") {
		refs.moderationMessage.textContent = message;
		refs.moderationMessage.dataset.mode = mode.toLowerCase().replace(/\s+/g, "-");
	}

	function setPasswordMessage(message, mode = "waiting") {
		refs.passwordMessage.textContent = message;
		refs.passwordMessage.dataset.mode = mode.toLowerCase().replace(/\s+/g, "-");
	}

	function setResetRequestMessage(message, mode = "waiting") {
		refs.resetRequestMessage.textContent = message;
		refs.resetRequestMessage.dataset.mode = mode.toLowerCase().replace(/\s+/g, "-");
	}

	function setResetPasswordMessage(message, mode = "waiting") {
		refs.resetPasswordMessage.textContent = message;
		refs.resetPasswordMessage.dataset.mode = mode.toLowerCase().replace(/\s+/g, "-");
	}

	function updateResetPanelVisibility() {
		if (!refs.resetPanel) {
			return;
		}
		refs.resetPanel.classList.toggle("hidden", !resetToken);
	}

	function readFormIntoAccount() {
		if (!currentAccount) {
			return;
		}
		currentAccount.display_name = refs.displayName.value.trim() || "Test Subject";
		currentAccount.suit_preset_index = clampPreset(refs.suitPreset.value);
		currentAccount.accent_preset_index = clampPreset(refs.accentPreset.value);
		currentAccount.visor_preset_index = clampPreset(refs.visorPreset.value);
	}

	function renderAccount() {
		if (!currentAccount) {
			refs.portalLayout.classList.add("hidden");
			refs.authPanel.classList.remove("hidden");
			document.getElementById("bureau-account-json").textContent = "null";
			window.BUREAU_ACCOUNT = null;
			return;
		}

		refs.authPanel.classList.add("hidden");
		refs.portalLayout.classList.remove("hidden");
		refs.activeUsername.textContent = currentAccount.username;
		refs.displayName.value = currentAccount.display_name;
		refs.suitPreset.value = String(currentAccount.suit_preset_index);
		refs.accentPreset.value = String(currentAccount.accent_preset_index);
		refs.visorPreset.value = String(currentAccount.visor_preset_index);
		refs.sessionRole.textContent = roleLabels[currentAccount.role] || roleLabels.player;
		refs.sessionRole.className = `status-pill role-${currentAccount.role}`;
		refs.banLabel.textContent = currentAccount.banned ? "Banned" : "Active";
		refs.banLabel.dataset.banned = currentAccount.banned ? "true" : "false";

		const suitColor = suitColors[currentAccount.suit_preset_index];
		const accentColor = accentColors[currentAccount.accent_preset_index];
		const visorColor = visorColors[currentAccount.visor_preset_index];

		document.documentElement.style.setProperty("--preview-suit", suitColor);
		document.documentElement.style.setProperty("--preview-accent", accentColor);
		document.documentElement.style.setProperty("--preview-visor", visorColor);

		refs.previewHead.style.background = suitColor;
		refs.previewBodyCore.style.background = suitColor;
		refs.previewChest.style.background = accentColor;
		refs.legendSuit.style.background = suitColor;
		refs.legendAccent.style.background = accentColor;
		refs.legendVisor.style.background = visorColor;
		refs.jsonPreview.textContent = JSON.stringify(currentAccount, null, 2);
		document.getElementById("bureau-account-json").textContent = JSON.stringify(currentAccount);
		window.BUREAU_ACCOUNT = { ...currentAccount };
		document.title = `${currentAccount.display_name} | Bureau Account Portal`;
	}

	function canManageRole(target) {
		return currentAccount && currentAccount.role === "director" && target.account_id !== currentAccount.account_id;
	}

	function canBanTarget(target) {
		if (!currentAccount || (currentAccount.role !== "director" && currentAccount.role !== "moderator")) {
			return false;
		}
		if (target.account_id === currentAccount.account_id) {
			return false;
		}
		if (target.role === "director" || target.role === "moderator") {
			return false;
		}
		return true;
	}

	function formatAuditTime(timestamp) {
		if (!timestamp) {
			return "Unknown time";
		}
		return new Date(Number(timestamp) * 1000).toLocaleString();
	}

	function formatBytes(value) {
		const size = Number(value) || 0;
		if (size <= 0) {
			return "Unknown size";
		}
		if (size < 1024) {
			return `${size} B`;
		}
		if (size < 1024 * 1024) {
			return `${(size / 1024).toFixed(1)} KB`;
		}
		if (size < 1024 * 1024 * 1024) {
			return `${(size / (1024 * 1024)).toFixed(1)} MB`;
		}
		return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`;
	}

	function renderAuditLog() {
		const searchTerm = refs.auditSearch ? refs.auditSearch.value.trim().toLowerCase() : "";
		const filteredAuditLog = auditLog.filter((entry) => {
			if (!searchTerm) {
				return true;
			}
			const haystack = [
				entry.actor_username,
				entry.actor_role,
				entry.target_username,
				entry.action,
				entry.reason,
				entry.remote_ip,
				entry.actor_account_id,
				entry.target_account_id
			].join(" ").toLowerCase();
			return haystack.includes(searchTerm);
		});
		refs.auditCount.textContent = `${filteredAuditLog.length} entr${filteredAuditLog.length === 1 ? "y" : "ies"}`;
		if (!currentAccount || (currentAccount.role !== "director" && currentAccount.role !== "moderator")) {
			refs.auditLog.className = "account-list empty-state";
			refs.auditLog.textContent = "Sign in as a moderator or the Director to review moderation history.";
			return;
		}
		if (filteredAuditLog.length === 0) {
			refs.auditLog.className = "account-list empty-state";
			refs.auditLog.textContent = searchTerm ? "No audit entries matched that search." : "No moderation actions have been recorded yet.";
			return;
		}
		refs.auditLog.className = "account-list";
		refs.auditLog.innerHTML = "";
		for (const entry of filteredAuditLog) {
			const row = document.createElement("div");
			row.className = "audit-row";

			const title = document.createElement("div");
			title.className = "audit-row-title";
			title.textContent = `${entry.actor_username} (${entry.actor_role}) -> ${entry.action} -> ${entry.target_username}`;

			const meta = document.createElement("div");
			meta.className = "audit-row-meta";
			const reason = entry.reason ? ` · reason: ${entry.reason}` : "";
			meta.textContent = `${formatAuditTime(entry.created_at)} · IP ${entry.remote_ip} · actor ${entry.actor_account_id} · target ${entry.target_account_id}${reason}`;

			row.appendChild(title);
			row.appendChild(meta);
			refs.auditLog.appendChild(row);
		}
	}

	function renderRegistry() {
		refs.accountCount.textContent = `${accountRegistry.length} account${accountRegistry.length === 1 ? "" : "s"}`;
		if (!currentAccount || (currentAccount.role !== "director" && currentAccount.role !== "moderator")) {
			refs.accountList.className = "account-list empty-state";
			refs.accountList.textContent = "Sign in as a moderator or the Director to view the account registry.";
			setAdminState("No Access", "offline");
			setModerationMessage("Only moderators and the Director can view registry actions.", "offline");
			renderAuditLog();
			return;
		}

		setAdminState(roleLabels[currentAccount.role] || "Access", "connected");
		setModerationMessage("Re-enter your moderator or Director username and password above before using moderation actions.", "connected");
		refs.accountList.className = "account-list";
		refs.accountList.innerHTML = "";

		for (const account of accountRegistry) {
			const row = document.createElement("div");
			row.className = "account-row";
			if (account.banned) {
				row.dataset.banned = "true";
			}

			const info = document.createElement("div");
			info.className = "account-row-info";

			const title = document.createElement("div");
			title.className = "account-row-title";
			title.textContent = account.display_name;

			const badge = document.createElement("span");
			badge.className = `role-badge role-${account.role}`;
			badge.textContent = roleLabels[account.role] || roleLabels.player;
			title.appendChild(badge);

			const meta = document.createElement("div");
			meta.className = "account-row-meta";
			meta.textContent = `${account.username} · ${account.account_id} · ${account.banned ? "Banned" : "Active"}`;

			info.appendChild(title);
			info.appendChild(meta);

			const actions = document.createElement("div");
			actions.className = "account-row-actions";

			if (canManageRole(account)) {
				const roleButton = document.createElement("button");
				roleButton.className = "mini-button";
				roleButton.type = "button";
				roleButton.textContent = account.role === "moderator" ? "Remove Mod" : "Make Mod";
				roleButton.addEventListener("click", () => updateModeration(account.account_id, account.role === "moderator" ? "demote_moderator" : "promote_moderator"));
				actions.appendChild(roleButton);
			}

			if (canBanTarget(account)) {
				const banButton = document.createElement("button");
				banButton.className = "mini-button";
				banButton.type = "button";
				banButton.textContent = account.banned ? "Unban" : "Ban";
				banButton.addEventListener("click", () => updateModeration(account.account_id, account.banned ? "unban" : "ban"));
				actions.appendChild(banButton);
			}

			row.appendChild(info);
			row.appendChild(actions);
			refs.accountList.appendChild(row);
		}

		renderAuditLog();
	}

	function renderPublishedLevels() {
		refs.levelsCount.textContent = `${publishedLevels.length} release${publishedLevels.length === 1 ? "" : "s"}`;
		if (!Array.isArray(publishedLevels) || publishedLevels.length === 0) {
			refs.levelsList.className = "account-list empty-state";
			refs.levelsList.textContent = "No released chambers have been listed yet.";
			return;
		}
		refs.levelsList.className = "account-list";
		refs.levelsList.innerHTML = "";
		for (const level of publishedLevels) {
			const row = document.createElement("div");
			row.className = "level-row";

			const title = document.createElement("div");
			title.className = "level-row-title";
			title.textContent = level.name || "Community Chamber";

			const stars = document.createElement("span");
			stars.className = "level-stars";
			const difficulty = Number.parseInt(level.difficulty_stars, 10) || 1;
			stars.textContent = "★".repeat(Math.max(1, Math.min(5, difficulty)));
			title.appendChild(stars);

			const description = document.createElement("div");
			description.className = "account-row-meta";
			description.textContent = level.description || "User-made chamber";

			const meta = document.createElement("div");
			meta.className = "level-row-meta";
			meta.textContent = `Author: ${level.author_display_name || level.author_username || "Local Creator"} · Size: ${level.chamber_size || "small"} · Reward: ${level.token_reward || 10} tokens`;

			row.appendChild(title);
			row.appendChild(description);
			row.appendChild(meta);
			refs.levelsList.appendChild(row);
		}
	}

	function renderAvailableBuilds() {
		refs.buildsCount.textContent = `${availableBuilds.length} build${availableBuilds.length === 1 ? "" : "s"}`;
		if (!Array.isArray(availableBuilds) || availableBuilds.length === 0) {
			refs.buildsList.className = "account-list empty-state";
			refs.buildsList.textContent = "No public beta downloads are available yet.";
			return;
		}
		refs.buildsList.className = "account-list";
		refs.buildsList.innerHTML = "";
		for (const build of availableBuilds) {
			const row = document.createElement("div");
			row.className = "account-row";

			const info = document.createElement("div");
			info.className = "account-row-info";

			const title = document.createElement("div");
			title.className = "account-row-title";
			title.textContent = build.name || build.filename || "Bureau Beta Build";

			const meta = document.createElement("div");
			meta.className = "account-row-meta";
			const updatedAt = build.updated_at ? new Date(Number(build.updated_at) * 1000).toLocaleString() : "Unknown time";
			meta.textContent = `${build.filename || "download.zip"} · ${formatBytes(build.size_bytes)} · Updated ${updatedAt}`;

			info.appendChild(title);
			info.appendChild(meta);

			const actions = document.createElement("div");
			actions.className = "account-row-actions";
			const downloadLink = document.createElement("a");
			downloadLink.className = "mini-button";
			downloadLink.href = build.url || "#";
			downloadLink.textContent = "Download";
			downloadLink.setAttribute("download", build.filename || "");
			actions.appendChild(downloadLink);

			row.appendChild(info);
			row.appendChild(actions);
			refs.buildsList.appendChild(row);
		}
	}

	async function loadPortalMetadata() {
		try {
			const payload = await requestJson("/healthz", {
				method: "GET",
				headers: {
					"Accept": "application/json"
				}
			});
			if (refs.portalAddress) {
				refs.portalAddress.textContent = window.location.host || "Portal Online";
			}
			if (refs.portalNote) {
				refs.portalNote.textContent = payload.registration_enabled
					? "Sign in here to manage your Bureau account and release community chambers."
					: "This portal is live, but new account registration is currently disabled.";
			}
			if (refs.registerButton) {
				refs.registerButton.disabled = !payload.registration_enabled;
			}
		} catch (_error) {
			if (refs.portalAddress) {
				refs.portalAddress.textContent = window.location.host || "Portal Offline";
			}
			if (refs.portalNote) {
				refs.portalNote.textContent = "The portal is reachable, but live service metadata could not be loaded.";
			}
		}
	}

	async function fetchPublishedLevels() {
		try {
			const payload = await requestJson("/api/levels", {
				method: "GET",
				headers: {
					"Accept": "application/json"
				}
			});
			publishedLevels = Array.isArray(payload.levels) ? payload.levels : [];
			renderPublishedLevels();
		} catch (_error) {
			publishedLevels = [];
			renderPublishedLevels();
		}
	}

	async function fetchAvailableBuilds() {
		try {
			const payload = await requestJson("/api/builds", {
				method: "GET",
				headers: {
					"Accept": "application/json"
				}
			});
			availableBuilds = Array.isArray(payload.builds) ? payload.builds : [];
			renderAvailableBuilds();
		} catch (_error) {
			availableBuilds = [];
			renderAvailableBuilds();
		}
	}

	async function requestJson(path, options = {}) {
		const response = await fetch(path, options);
		const text = await response.text();
		let payload = {};
		try {
			payload = JSON.parse(text);
		} catch (_error) {
			payload = {};
		}
		if (!response.ok) {
			throw new Error(payload.error || `HTTP ${response.status}`);
		}
		return payload;
	}

	function applyPortalPayload(payload) {
		currentAccount = normalizeAccount(payload.account);
		accountRegistry = Array.isArray(payload.accounts) ? payload.accounts.map(normalizeAccount) : [];
		auditLog = Array.isArray(payload.audit_log) ? payload.audit_log : [];
		renderAccount();
		renderRegistry();
	}

	async function login(username, password) {
		const payload = await requestJson("/api/auth/login", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"Accept": "application/json"
			},
			body: JSON.stringify({ username, password })
		});
		currentSession.username = username;
		currentSession.password = password;
		currentSession.token = payload.session && payload.session.token ? payload.session.token : "";
		applyPortalPayload(payload);
		setStatus(`Signed in as ${currentAccount.display_name}.`, "Connected");
	}

	async function handleLogin() {
		if (!hasAcceptedTos()) {
			updateTosVisibility();
			setStatus("Accept the Terms of Service before signing in.", "Offline");
			return;
		}
		try {
			await login(refs.loginUsername.value.trim(), refs.loginPassword.value);
		} catch (error) {
			setStatus(`Sign in failed. ${error.message}`, "Offline");
		}
	}

	async function handleRegister() {
		if (!hasAcceptedTos()) {
			updateTosVisibility();
			setStatus("Accept the Terms of Service before creating an account.", "Offline");
			return;
		}
		if (!refs.registerAcceptTos.checked) {
			setStatus("Check the Terms of Service confirmation before creating an account.", "Offline");
			return;
		}
		try {
			const payload = await requestJson("/api/auth/register", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Accept": "application/json"
				},
				body: JSON.stringify({
					username: refs.registerUsername.value.trim(),
					password: refs.registerPassword.value,
					display_name: refs.registerDisplayName.value.trim(),
					accept_tos: true
				})
			});
			currentSession.username = refs.registerUsername.value.trim();
			currentSession.password = refs.registerPassword.value;
			currentSession.token = payload.session && payload.session.token ? payload.session.token : "";
			applyPortalPayload(payload);
			setStatus(`Created and signed in as ${currentAccount.display_name}.`, "Connected");
		} catch (error) {
			setStatus(`Registration failed. ${error.message}`, "Offline");
		}
	}

	async function requestPasswordReset() {
		const username = refs.resetRequestUsername.value.trim();
		if (!username) {
			setResetRequestMessage("Enter your username before requesting a reset link.", "offline");
			return;
		}
		try {
			const payload = await requestJson("/api/auth/request-password-reset", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Accept": "application/json"
				},
				body: JSON.stringify({ username })
			});
			setResetRequestMessage(payload.message || "If that account exists, a reset link has been prepared.", "connected");
			if (payload.reset_url) {
				refs.resetRequestLink.href = payload.reset_url;
				refs.resetRequestLink.textContent = payload.reset_url;
				refs.resetRequestPreview.classList.remove("hidden");
			} else {
				refs.resetRequestLink.href = "#";
				refs.resetRequestLink.textContent = "Reset link preview is disabled in this environment.";
				refs.resetRequestPreview.classList.add("hidden");
			}
		} catch (error) {
			setResetRequestMessage(`Reset link request failed. ${error.message}`, "offline");
		}
	}

	async function finishPasswordReset() {
		if (!resetToken) {
			setResetPasswordMessage("No reset token was found in this link.", "offline");
			return;
		}
		const newPassword = refs.resetNewPassword.value;
		const confirmNewPassword = refs.resetConfirmPassword.value;
		if (!newPassword || !confirmNewPassword) {
			setResetPasswordMessage("Enter and confirm your new password before submitting.", "offline");
			return;
		}
		try {
			const payload = await requestJson("/api/auth/reset-password", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Accept": "application/json"
				},
				body: JSON.stringify({
					token: resetToken,
					new_password: newPassword,
					confirm_new_password: confirmNewPassword
				})
			});
			refs.resetNewPassword.value = "";
			refs.resetConfirmPassword.value = "";
			setResetPasswordMessage(payload.message || "Password reset complete.", "connected");
			setStatus(payload.message || "Password reset complete.", "Connected");
			const cleanUrl = `${window.location.origin}${window.location.pathname}`;
			window.history.replaceState({}, document.title, cleanUrl);
		} catch (error) {
			setResetPasswordMessage(`Password reset failed. ${error.message}`, "offline");
			setStatus(`Password reset failed. ${error.message}`, "Offline");
		}
	}

	async function saveProfile() {
		if (!currentAccount) {
			return;
		}
		readFormIntoAccount();
		try {
			const payload = await requestJson("/api/account", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Accept": "application/json",
					"X-Session-Token": currentSession.token || ""
				},
				body: JSON.stringify({
					session_token: currentSession.token || "",
					display_name: currentAccount.display_name,
					suit_preset_index: currentAccount.suit_preset_index,
					accent_preset_index: currentAccount.accent_preset_index,
					visor_preset_index: currentAccount.visor_preset_index
				})
			});
			applyPortalPayload({
				account: payload.account,
				accounts: payload.accounts || accountRegistry,
				audit_log: payload.audit_log || auditLog
			});
			setStatus("Profile saved.", "Connected");
		} catch (error) {
			setStatus(`Profile save failed. ${error.message}`, "Offline");
		}
	}

	async function changePassword() {
		if (!currentAccount) {
			return;
		}
		const currentPassword = refs.currentPassword.value;
		const newPassword = refs.newPassword.value;
		const confirmNewPassword = refs.confirmNewPassword.value;
		if (!currentPassword || !newPassword || !confirmNewPassword) {
			setPasswordMessage("Fill out all three password fields before updating your password.", "offline");
			return;
		}
		try {
			const payload = await requestJson("/api/account/password", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Accept": "application/json",
					"X-Session-Token": currentSession.token || ""
				},
				body: JSON.stringify({
					session_token: currentSession.token || "",
					current_password: currentPassword,
					new_password: newPassword,
					confirm_new_password: confirmNewPassword
				})
			});
			currentSession.password = newPassword;
			if (payload.session && payload.session.token) {
				currentSession.token = payload.session.token;
			}
			refs.currentPassword.value = "";
			refs.newPassword.value = "";
			refs.confirmNewPassword.value = "";
			applyPortalPayload({
				account: payload.account,
				accounts: payload.accounts || accountRegistry,
				audit_log: payload.audit_log || auditLog
			});
			setStatus(payload.message || "Password updated.", "Connected");
			setPasswordMessage(payload.message || "Password updated.", "connected");
		} catch (error) {
			setStatus(`Password update failed. ${error.message}`, "Offline");
			setPasswordMessage(`Password update failed. ${error.message}`, "offline");
		}
	}

	async function updateModeration(targetAccountId, action) {
		const verificationUsername = refs.moderationUsername.value.trim();
		const verificationPassword = refs.moderationPassword.value;
		const reason = refs.moderationReason.value.trim();
		if (!verificationUsername || !verificationPassword || !reason) {
			setModerationMessage("Enter your moderator or Director username, password, and a moderation reason before using moderation actions.", "offline");
			return;
		}
		try {
			const payload = await requestJson("/api/moderation", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"Accept": "application/json",
					"X-Session-Token": currentSession.token || ""
				},
				body: JSON.stringify({
					session_token: currentSession.token || "",
					target_account_id: targetAccountId,
					action,
					verification_username: verificationUsername,
					verification_password: verificationPassword,
					reason
				})
			});
			accountRegistry = Array.isArray(payload.accounts) ? payload.accounts.map(normalizeAccount) : [];
			auditLog = Array.isArray(payload.audit_log) ? payload.audit_log : auditLog;
			refs.moderationReason.value = "";
			renderRegistry();
			setStatus(payload.message || "Registry updated.", "Connected");
			setModerationMessage(payload.message || "Moderation action completed.", "connected");
		} catch (error) {
			setStatus(`Moderation update failed. ${error.message}`, "Offline");
			setModerationMessage(`Moderation update failed. ${error.message}`, "offline");
		}
	}

	async function copyJson() {
		if (!currentAccount) {
			return;
		}
		try {
			await navigator.clipboard.writeText(JSON.stringify(currentAccount, null, 2));
			setStatus("Account JSON copied to clipboard.", "Connected");
		} catch (_error) {
			setStatus("Account JSON could not be copied automatically.", "Offline");
		}
	}

	async function logout() {
		if (currentSession.token) {
			try {
				await requestJson("/api/auth/logout", {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
						"Accept": "application/json",
						"X-Session-Token": currentSession.token
					},
					body: JSON.stringify({ session_token: currentSession.token })
				});
			} catch (_error) {
			}
		}
		currentSession = { username: "", password: "", token: "" };
		currentAccount = null;
		accountRegistry = [];
		auditLog = [];
		refs.loginPassword.value = "";
		refs.currentPassword.value = "";
		refs.newPassword.value = "";
		refs.confirmNewPassword.value = "";
		refs.moderationUsername.value = "";
		refs.moderationPassword.value = "";
		refs.moderationReason.value = "";
		renderAccount();
		renderRegistry();
		setStatus("Signed out.", "Waiting");
		setPasswordMessage("Use your current password and a new password with at least 8 characters.", "waiting");
		setModerationMessage("Sign in as a moderator or the Director, then enter your username and password here before using ban or unban.", "waiting");
	}

	refs.tosAcceptButton.addEventListener("click", acceptTos);
	refs.tosDeclineButton.addEventListener("click", declineTos);
	refs.loginButton.addEventListener("click", handleLogin);
	refs.registerButton.addEventListener("click", handleRegister);
	refs.requestResetButton.addEventListener("click", requestPasswordReset);
	refs.resetPasswordButton.addEventListener("click", finishPasswordReset);
	refs.saveButton.addEventListener("click", saveProfile);
	refs.changePasswordButton.addEventListener("click", changePassword);
	refs.copyJsonButton.addEventListener("click", copyJson);
	refs.logoutButton.addEventListener("click", logout);
	if (refs.refreshLevelsButton) {
		refs.refreshLevelsButton.addEventListener("click", fetchPublishedLevels);
	}
	if (refs.refreshBuildsButton) {
		refs.refreshBuildsButton.addEventListener("click", fetchAvailableBuilds);
	}
	if (refs.auditSearch) {
		refs.auditSearch.addEventListener("input", renderAuditLog);
	}

	[refs.displayName, refs.suitPreset, refs.accentPreset, refs.visorPreset].forEach((element) => {
		element.addEventListener("input", readFormIntoAccount);
		element.addEventListener("change", readFormIntoAccount);
	});

	updateTosVisibility();
	updateResetPanelVisibility();
	renderAccount();
	renderRegistry();
	loadPortalMetadata();
	fetchPublishedLevels();
	fetchAvailableBuilds();
	setStatus("Sign in or create an account to open the account portal.", "Waiting");
	setResetRequestMessage("Use your username to prepare a one-time password reset link.", "waiting");
	setResetPasswordMessage("Reset links expire automatically after a short time.", "waiting");
	setPasswordMessage("Use your current password and a new password with at least 8 characters.", "waiting");
	setModerationMessage("Sign in as a moderator or the Director, then enter your username and password here before using ban or unban.", "waiting");
})();
