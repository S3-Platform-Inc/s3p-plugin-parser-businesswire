import datetime
import time

from s3p_sdk.exceptions.parser import S3PPluginParserOutOfRestrictionException, S3PPluginParserFinish
from s3p_sdk.plugin.payloads.parsers import S3PParserBase
from s3p_sdk.types import S3PRefer, S3PDocument, S3PPlugin
from s3p_sdk.types.plugin_restrictions import FROM_DATE, S3PPluginRestrictions
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from random import uniform

import dateparser


class BUSINESSWIRE(S3PParserBase):
    """
    A Parser payload that uses S3P Parser base class.
    """
    HOST = 'https://www.businesswire.com/portal/site/home/news/'

    def __init__(self, refer: S3PRefer, plugin: S3PPlugin, web_driver: WebDriver, restrictions: S3PPluginRestrictions):
        super().__init__(refer, plugin, restrictions)

        # Тут должны быть инициализированы свойства, характерные для этого парсера. Например: WebDriver
        self._driver = web_driver
        self._wait = WebDriverWait(self._driver, timeout=20)

    def _parse(self, abstract=None):
        """
        Метод, занимающийся парсингом. Он добавляет в _content_document документы, которые получилось обработать
        :return:
        :rtype:
        """
        # HOST - это главная ссылка на источник, по которому будет "бегать" парсер
        self.logger.debug(F"Parser enter to {self.HOST}")

        self._driver.get(self.HOST)  # Открыть страницу со списком businesswire в браузере
        self._wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, '.bwNewsList')))

        while len(self._driver.find_elements(By.CLASS_NAME, 'pagingNext')) > 0:
            self._wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, '.bwNewsList')))
            el_list = self._driver.find_element(By.CLASS_NAME, 'bwNewsList').find_elements(By.TAG_NAME, 'li')
            for el in el_list:
                try:
                    article_link = el.find_element(By.CLASS_NAME, 'bwTitleLink')
                    web_link = article_link.get_attribute('href')
                    title = article_link.text
                    pub_date = dateparser.parse(el.find_element(By.TAG_NAME, 'time').get_attribute('datetime'))
                    self._driver.execute_script("window.open('');")
                    self._driver.switch_to.window(self._driver.window_handles[1])
                    time.sleep(uniform(0.1, 1.2))
                    self._driver.get(web_link)
                    self._wait.until(ec.presence_of_element_located((By.CSS_SELECTOR, '.bw-release-story')))
                    text_content = self._driver.find_element(By.CLASS_NAME, 'bw-release-story').text
                except Exception as e:
                    self.logger.warning(f'The Article cannot be parsed. Error: {e}')
                else:
                    document = S3PDocument(
                        id=None,
                        title=title,
                        abstract=abstract if abstract else None,
                        text=text_content,
                        link=web_link,
                        storage=None,
                        other=None,
                        published=pub_date,
                        loaded=None,
                    )
                    # Логирование найденного документа
                    try:
                        self._find(document)
                    except S3PPluginParserOutOfRestrictionException as e:
                        if e.restriction == FROM_DATE:
                            self.logger.debug(f'Document is out of date range `{self._restriction.from_date}`')
                            raise S3PPluginParserFinish(self._plugin,
                                                        f'Document is out of date range `{self._restriction.from_date}`',
                                                        e)

                    self._driver.close()
                    self._driver.switch_to.window(self._driver.window_handles[0])
                    time.sleep(uniform(0.3, 1))
            try:
                self._driver.get(
                    self._driver.find_element(By.CLASS_NAME, 'pagingNext').find_element(By.TAG_NAME, 'a').get_attribute(
                        'href'))
            except:
                self.logger.info('Не найдено перехода на след. страницу. Завершение...')
                break

    def _initial_access_source(self, url: str, delay: int = 2):
        self._driver.get(url)
        self.logger.debug('Entered on web page ' + url)
        time.sleep(delay)
        self._agree_cookie_pass()

    def _agree_cookie_pass(self):
        """
        Метод прожимает кнопку agree на модальном окне
        """
        cookie_agree_xpath = '//*[@id="onetrust-accept-btn-handler"]'

        try:
            cookie_button = self._driver.find_element(By.XPATH, cookie_agree_xpath)
            if WebDriverWait(self._driver, 5).until(ec.element_to_be_clickable(cookie_button)):
                cookie_button.click()
                self.logger.debug(F"Parser pass cookie modal on page: {self._driver.current_url}")
        except NoSuchElementException as e:
            self.logger.debug(f'modal agree not found on page: {self._driver.current_url}')
