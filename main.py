import asyncio
import base64
import logging

import orjson as json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import ORJSONResponse
from playwright import async_api
from playwright.async_api import Playwright, Browser as BrowserProcess, Page
from pydantic import BaseModel

with open('config.json', 'r') as f:
    config = json.loads(f.read())

app = FastAPI()
logger = logging.getLogger("uvicorn")


class ScreenshotOptions(BaseModel):
    content: str = None
    width: int = 500
    height: int = 1000
    mw: bool = False
    tracing: bool = False


class ElementScreenshotOptions(BaseModel):
    element: str | list = None
    content: str = None
    url: str = None
    css: str = None
    width: int = 1280
    height: int = 720
    counttime: bool = False
    tracing: bool = False


class SectionScreenshotOptions(BaseModel):
    section: str | list = None
    content: str = None
    url: str = None
    css: str = None
    width: int = 1280
    height: int = 720
    counttime: bool = False
    tracing: bool = False


# 自定义CSS


class Browser:
    playwright: Playwright = None
    browser: BrowserProcess = None

    @classmethod
    async def browser_init(cls):
        if not cls.playwright and not cls.browser:
            logger.info('Launching browser...')
            cls.playwright = await async_api.async_playwright().start()
            cls.browser = await cls.playwright.firefox.launch(headless=True)
            while not cls.browser:
                await asyncio.sleep(1)
            logger.info('Successfully launched browser.')

    @classmethod
    async def close(cls):
        await cls.browser.close()


class Templates():
    @staticmethod
    def content(contents: str):
        content_plate = f"""<link rel="preconnect" href="https://fonts.googleapis.com">
              <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
              <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+HK&family=Noto+Sans+JP&family=Noto+Sans+KR&family=Noto+Sans+SC&family=Noto+Sans+TC&display=swap" rel="stylesheet"><style>html body {{
                margin-top: 0px !important;
                font-family: 'Noto Sans SC', sans-serif;
            }}

            :lang(ko) {{
                font-family: 'Noto Sans KR', 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', sans-serif;
            }}

            :lang(ja) {{
                font-family: 'Noto Sans JP', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
            }}

            :lang(zh-TW) {{
                font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
            }}

            :lang(zh-HK) {{
                font-family: 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans SC', 'Noto Sans KR', sans-serif;
            }}

            :lang(zh-Hans), :lang(zh-CN), :lang(zh) {{
                font-family:  'Noto Sans SC', 'Noto Sans HK', 'Noto Sans TC', 'Noto Sans JP', 'Noto Sans KR', sans-serif;
            }}

            div.infobox div.notaninfobox{{
                width: 100%!important;
                float: none!important;
                margin: 0 0 0 0!important;
            }}

            table.infobox, table.infoboxSpecial, table.moe-infobox {{
                width: 100%!important;
                float: unset!important;
                margin: 0 0 0 0!important;
            }}</style>
            <meta charset="UTF-8">
            <body>
            {contents}
            </body>
            """
        return content_plate

    @staticmethod
    def custom_css():
        custom_css = """
        span.heimu a.external, span.heimu a.external:visited, span.heimu a.extiw, span.heimu a.extiw:visited {
          color: #252525;}
        .heimu, .heimu a, a .heimu, .heimu a.new {
          background-color: #cccccc;
          text-shadow: none;
        }
        .tabber-container-infobox ul.tabbernav {
          display: none;
        }
        .tabber-container-infobox .tabber .tabbertab {
          display: unset !important;
        }
        """
        return custom_css


async def is_avail(el: int | list, pg: Page):
    if isinstance(el, str):
        return el
    else:
        for obj in el:
            rtn = await pg.query_selector(str(obj))
            if rtn:
                return str(obj)
            break


async def make_screenshot(page: Page, el: Page.query_selector):
    await page.evaluate("window.scroll(0, 0)")
    images = []
    img = await el.screenshot(type='png')
    images.append(base64.b64encode(img).decode())
    return images


@app.post("/")
async def _screenshot(options: ScreenshotOptions):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    await page.set_viewport_size({'width': options.width, 'height': options.height})
    await page.set_content(Templates().content(options.content), wait_until='networkidle')
    if options.mw:
        selector = 'body > .mw-parser-output > *:not(script):not(style):not(link):not(meta)'
    else:
        selector = 'body > *:not(script):not(style):not(link):not(meta)'
    element_ = await page.query_selector(selector)
    images = await make_screenshot(page, element_)
    await page.close()
    return ORJSONResponse(content=images)


@app.post("/page/")
async def page_screenshot(url: str = None, css: str = None):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    await page.goto(url, wait_until="networkidle")
    if css:
        await page.add_style_tag(content=css + Templates().custom_css())
    screenshot = await make_screenshot(page, await page.query_selector("body"))
    await page.close()
    return ORJSONResponse(content=screenshot)


@app.post("/element_screenshot/")
async def element_screenshot(options: ElementScreenshotOptions):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    await page.set_viewport_size({'width': options.width, 'height': options.height})
    if options.content:
        await page.set_content(options.content)
    else:
        await page.goto(options.url, wait_until="networkidle")
    if options.css:
        await page.add_style_tag(content=options.css + Templates().custom_css())
    el = await page.query_selector(await is_avail(options.element, page))
    if not el:
        raise HTTPException(status_code=404, detail="Element not found")
    images = await make_screenshot(page, el)
    await page.close()
    return ORJSONResponse(content=images)


@app.post("/section_screenshot/")
async def section_screenshot(options: SectionScreenshotOptions):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    await page.set_viewport_size({'width': options.width, 'height': options.height})
    if options.content:
        await page.set_content(options.content)
    else:
        await page.goto(options.url, wait_until="networkidle")
    if options.css:
        await page.add_style_tag(content=options.css + Templates().custom_css())
    section = await page.query_selector(await is_avail(options.section, page))
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    images = await make_screenshot(page, section)
    await page.close()
    return ORJSONResponse(content=images)


@app.get("/source/")
async def source(request: Request):
    await Browser.browser_init()
    page = await Browser.browser.new_page()
    try:
        url = request.query_params.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL parameter is required")

        await page.goto(url, wait_until="networkidle")
        _source = await page.content()

        return ORJSONResponse(content={"source": _source})
    finally:
        await page.close()


if __name__ == "__main__":
    import uvicorn

    try:
        loop = asyncio.new_event_loop()
        logger.info(f"Server starting on {config['server']['host']}:{config['server']['port']}")
        loop.run_until_complete(uvicorn.run(app, host=config["server"]["host"], port=config["server"]["port"]))
    except KeyboardInterrupt:
        logger.info("Server stopped")
        asyncio.run(Browser.close())
