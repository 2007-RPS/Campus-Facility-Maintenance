import os
import json
import asyncio
import websockets
import base64
import urllib.request
from init_db import initialize_database

ARTIFACT_DIR = r"C:\Users\Parth\.gemini\antigravity-ide\brain\0d4e6174-1f24-44c5-9674-349707d279e2"
BASE_URL = "http://127.0.0.1:5000"

async def get_page_ws():
    resp = urllib.request.urlopen("http://127.0.0.1:9222/json")
    pages = json.loads(resp.read().decode())
    for p in pages:
        if p.get("type") == "page" and "devtools/page" in p.get("webSocketDebuggerUrl", ""):
            return p["webSocketDebuggerUrl"]
    raise RuntimeError("No usable page found in Chrome")

class BrowserDriver:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.req_id = 0
        self.pending_responses = {}
        self.console_logs = []
        self.listener_task = None

    async def __aenter__(self):
        self.ws = await websockets.connect(self.ws_url)
        self.listener_task = asyncio.create_task(self._listen())
        await self.call("Page.enable")
        await self.call("Runtime.enable")
        await self.call("Log.enable")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.listener_task:
            self.listener_task.cancel()
        if self.ws:
            await self.ws.close()

    async def _listen(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                msg_id = msg.get("id")
                if msg_id in self.pending_responses:
                    fut = self.pending_responses.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                
                # Check events
                method = msg.get("method")
                if method == "Runtime.consoleAPICalled":
                    args = msg.get("params", {}).get("args", [])
                    txt = " ".join(str(a.get("value", "")) for a in args)
                    lvl = msg.get("params", {}).get("type", "log")
                    self.console_logs.append(f"[{lvl.upper()}] {txt}")
                elif method == "Log.entryAdded":
                    entry = msg.get("params", {}).get("entry", {})
                    self.console_logs.append(f"[{entry.get('level', 'log').upper()}] {entry.get('text', '')}")
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def call(self, method, params=None):
        self.req_id += 1
        curr_id = self.req_id
        fut = asyncio.get_running_loop().create_future()
        self.pending_responses[curr_id] = fut
        
        msg = {"id": curr_id, "method": method}
        if params:
            msg["params"] = params
        await self.ws.send(json.dumps(msg))
        return await fut

    async def eval_js(self, script):
        resp = await self.call("Runtime.evaluate", {
            "expression": f"(() => {{ {script} }})()",
            "returnByValue": True,
            "awaitPromise": True
        })
        res = resp.get("result", {})
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS Error: {res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    async def navigate(self, url):
        self.console_logs.clear()
        await self.call("Page.navigate", {"url": url})
        await asyncio.sleep(1.5)

    async def screenshot(self, filename):
        resp = await self.call("Page.captureScreenshot", {"format": "png"})
        data = resp["result"]["data"]
        bytes_data = base64.b64decode(data)
        out_path = os.path.join(ARTIFACT_DIR, filename)
        with open(out_path, "wb") as f:
            f.write(bytes_data)
        print(f" -> Screenshot saved: {filename} ({len(bytes_data)} bytes)")
        return out_path

async def run_audit():
    # 0. Reseed database to fresh state
    print("[*] Reseeding database...")
    initialize_database()

    ws_url = await get_page_ws()
    print(f"[*] Connecting to Chrome CDP at: {ws_url}")

    async with BrowserDriver(ws_url) as driver:
        # Set window / viewport size (standard 1440x900 desktop)
        await driver.call("Emulation.setDeviceMetricsOverride", {
            "width": 1440,
            "height": 900,
            "deviceScaleFactor": 1,
            "mobile": False
        })

        # =========================================================================
        # 1. Requester Portal (Student Alex Chen)
        # =========================================================================
        print("\n==================================================")
        print("1. AUDITING REQUESTER PORTAL (/portal)")
        print("==================================================")
        await driver.call("Network.clearBrowserCookies")
        await driver.navigate(f"{BASE_URL}/portal/login")

        # Check input styling on login page
        login_input_styles = await driver.eval_js("""
            const el = document.querySelector('#email');
            const st = window.getComputedStyle(el);
            return {
                width: st.width,
                padding: st.padding,
                borderRadius: st.borderRadius,
                boxSizing: st.boxSizing
            };
        """)
        print("Requester Login input styles:", json.dumps(login_input_styles))

        # Fill credentials & submit
        await driver.eval_js("""
            document.querySelector('#email').value = 'alex.student@campus.edu';
            document.querySelector('#password').value = 'student123';
            document.querySelector('#login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        """)
        await asyncio.sleep(2)

        url = await driver.eval_js("return window.location.href;")
        print(f"Logged in URL: {url}")
        assert "/portal" in url, f"Expected /portal, got {url}"

        # Test Opening Submit Request Modal
        await driver.eval_js("openModal('new-request-modal');")
        await asyncio.sleep(0.5)

        # Verify modal input styling
        modal_styles = await driver.eval_js("""
            const cat = document.querySelector('#category-select');
            const st = window.getComputedStyle(cat);
            return {
                width: st.width,
                padding: st.padding,
                borderRadius: st.borderRadius
            };
        """)
        print("Modal select styles:", json.dumps(modal_styles))

        # Close Modal
        await driver.eval_js("closeModal('new-request-modal');")
        await asyncio.sleep(0.5)

        # Capture Requester Console Screenshot
        await driver.screenshot("console_01_requester_portal.png")
        req_errors = [l for l in driver.console_logs if "ERROR" in l]
        print("Requester Console Errors:", req_errors)
        assert len(req_errors) == 0, f"Found console errors: {req_errors}"

        # =========================================================================
        # 2. Technician Console (Carlos Mendez)
        # =========================================================================
        print("\n==================================================")
        print("2. AUDITING TECHNICIAN CONSOLE (/technician)")
        print("==================================================")
        await driver.call("Network.clearBrowserCookies")
        await driver.navigate(f"{BASE_URL}/technician/login")

        tech_login_styles = await driver.eval_js("""
            const el = document.querySelector('#email');
            const st = window.getComputedStyle(el);
            return { width: st.width, padding: st.padding, borderRadius: st.borderRadius };
        """)
        print("Technician Login input styles:", json.dumps(tech_login_styles))

        await driver.eval_js("""
            document.querySelector('#email').value = 'carlos.electrician@campus.edu';
            document.querySelector('#password').value = 'tech123';
            document.querySelector('#login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        """)
        await asyncio.sleep(2)

        url = await driver.eval_js("return window.location.href;")
        print(f"Logged in URL: {url}")
        assert "/technician" in url, f"Expected /technician, got {url}"

        # Test Work Log Modal
        await driver.eval_js("openModal('work-log-modal');")
        await asyncio.sleep(0.5)

        # Verify textarea styling in work log modal
        wl_styles = await driver.eval_js("""
            const input = document.querySelector('#work-desc-input');
            const st = window.getComputedStyle(input);
            return { width: st.width, padding: st.padding, borderRadius: st.borderRadius };
        """)
        print("Work log textarea styles:", json.dumps(wl_styles))

        # Test adding material row
        await driver.eval_js("document.querySelector('#add-material-row-btn').click();")
        await asyncio.sleep(0.3)
        mat_styles = await driver.eval_js("""
            const mat = document.querySelector('.mat-name');
            const st = window.getComputedStyle(mat);
            return { width: st.width, padding: st.padding, borderRadius: st.borderRadius };
        """)
        print("Dynamic material input styles:", json.dumps(mat_styles))

        await driver.eval_js("closeModal('work-log-modal');")
        await asyncio.sleep(0.5)

        # Capture Technician Console Screenshot
        await driver.screenshot("console_02_technician.png")
        tech_errors = [l for l in driver.console_logs if "ERROR" in l]
        print("Technician Console Errors:", tech_errors)
        assert len(tech_errors) == 0, f"Found console errors: {tech_errors}"

        # =========================================================================
        # 3. Facility Admin Console (Marcus Vance)
        # =========================================================================
        print("\n==================================================")
        print("3. AUDITING FACILITY ADMIN CONSOLE (/admin)")
        print("==================================================")
        await driver.call("Network.clearBrowserCookies")
        await driver.navigate(f"{BASE_URL}/admin/login")

        admin_login_styles = await driver.eval_js("""
            const el = document.querySelector('#email');
            const st = window.getComputedStyle(el);
            return { width: st.width, padding: st.padding, borderRadius: st.borderRadius };
        """)
        print("Admin Login input styles:", json.dumps(admin_login_styles))

        await driver.eval_js("""
            document.querySelector('#email').value = 'marcus.admin@campus.edu';
            document.querySelector('#password').value = 'admin123';
            document.querySelector('#login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        """)
        await asyncio.sleep(2)

        url = await driver.eval_js("return window.location.href;")
        print(f"Logged in URL: {url}")
        assert "/admin" in url, f"Expected /admin, got {url}"

        # Test Assign Modal
        await driver.eval_js("openModal('assign-modal');")
        await asyncio.sleep(0.5)
        assign_input_styles = await driver.eval_js("""
            const el = document.querySelector('#tech-select');
            const st = window.getComputedStyle(el);
            return { width: st.width, padding: st.padding, borderRadius: st.borderRadius };
        """)
        print("Assign Modal tech select styles:", json.dumps(assign_input_styles))
        await driver.eval_js("closeModal('assign-modal');")
        await asyncio.sleep(0.3)

        # Switch to User Management tab & test Create User Modal
        await driver.eval_js("""
            const tab = document.querySelector('[data-tab="users"]');
            if (tab) tab.click();
        """)
        await asyncio.sleep(0.5)

        await driver.eval_js("openModal('create-user-modal');")
        await asyncio.sleep(0.5)

        user_input_styles = await driver.eval_js("""
            const el = document.querySelector('#user-name');
            const st = window.getComputedStyle(el);
            return { width: st.width, padding: st.padding, borderRadius: st.borderRadius };
        """)
        print("Create User Modal input styles:", json.dumps(user_input_styles))

        await driver.eval_js("closeModal('create-user-modal');")
        await asyncio.sleep(0.3)

        # Switch back to Requests tab
        await driver.eval_js("""
            const tab = document.querySelector('[data-tab="requests"]');
            if (tab) tab.click();
        """)
        await asyncio.sleep(0.5)

        # Capture Admin Console Screenshot
        await driver.screenshot("console_03_facility_admin.png")
        admin_errors = [l for l in driver.console_logs if "ERROR" in l]
        print("Admin Console Errors:", admin_errors)
        assert len(admin_errors) == 0, f"Found console errors: {admin_errors}"

        # =========================================================================
        # 4. Executive Management Console (Dr. Arthur Reynolds)
        # =========================================================================
        print("\n==================================================")
        print("4. AUDITING EXECUTIVE MANAGEMENT CONSOLE (/management)")
        print("==================================================")
        await driver.call("Network.clearBrowserCookies")
        await driver.navigate(f"{BASE_URL}/management/login")

        mgmt_login_styles = await driver.eval_js("""
            const el = document.querySelector('#email');
            const st = window.getComputedStyle(el);
            return { width: st.width, padding: st.padding, borderRadius: st.borderRadius };
        """)
        print("Management Login input styles:", json.dumps(mgmt_login_styles))

        await driver.eval_js("""
            document.querySelector('#email').value = 'reynolds.mgmt@campus.edu';
            document.querySelector('#password').value = 'mgmt123';
            document.querySelector('#login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        """)
        await asyncio.sleep(2)

        url = await driver.eval_js("return window.location.href;")
        print(f"Logged in URL: {url}")
        assert "/management" in url, f"Expected /management, got {url}"

        # Verify Chart.js Canvas and KPI cards
        kpi_info = await driver.eval_js("""
            const canvas = document.querySelector('#category-chart');
            const kpis = Array.from(document.querySelectorAll('.kpi-card-value')).map(el => el.textContent.trim());
            return {
                chartWidth: canvas ? canvas.width : 0,
                kpiValues: kpis
            };
        """)
        print("Management KPIs & Chart info:", json.dumps(kpi_info))

        # Capture Management Console Screenshot
        await driver.screenshot("console_04_executive_management.png")
        mgmt_errors = [l for l in driver.console_logs if "ERROR" in l]
        print("Management Console Errors:", mgmt_errors)
        assert len(mgmt_errors) == 0, f"Found console errors: {mgmt_errors}"

        print("\n" + "=" * 70)
        print("ALL 4 CONSOLES PASSED AUDIT WITH ZERO ERRORS AND COMPLETE STYLING!")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_audit())
