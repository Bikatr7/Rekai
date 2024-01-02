import concurrent.futures

from loguru import logger

from selenium import webdriver
# from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from time import sleep

# Google Cloud
from google.cloud import texttospeech

from Rekai.nlp_modules.basic_nlp import TextSplitter
from Rekai.appconfig import AppConfig
from Rekai.nlp_modules.japanese_nlp import Classifier
from Rekai.nlp_modules.basic_nlp import test_text as test_lines
from Rekai.nlp_modules.basic_nlp import test_text_2 as test_lines_2


class Transmute:
    logger.add(sink='')

    @staticmethod
    def parse_string_with_jisho(line: str, index: str = 0) -> str:

        """DOCSTRING PENDING"""

        driver = webdriver.Chrome()
        #
        jisho_parsed_html_element = str()

        if Classifier.contains_no_parsable_text(line):
            jisho_parsed_html_element += 'un-parsable'

        else:
            url = f'https://jisho.org/search/{line}'

            try:

                logger.info(f'Trying to parse line {index}')

                driver.get(url=url)
                logger.info(f'{index} - Webdriver instance Started')

                zen_bar_element = WebDriverWait(driver, 10).until(ec.visibility_of_element_located((By.ID, "zen_bar")))
                zen_outer_html = zen_bar_element.get_attribute('outerHTML')

                # Selenium also extracts linebreaks that mess with the html when assigned to a string
                zen_html = str(zen_outer_html).replace('\n', "").strip()

                jisho_parsed_html_element += zen_html

            except Exception as e:
                print('Element not found: ', e)
                logger.error(f'An exception occured in jisho parse - f{str(e)}')
                zen_html = f'<p>((Text is not parsable or could not be parsed))</p>'
                jisho_parsed_html_element += zen_html

            driver.quit()

        return jisho_parsed_html_element

    @staticmethod
    def parse_list_with_jisho(list_of_lines: list) -> list:

        """DOCSTING PENDING"""

        logger.info('JISHO AutoParse initialized')

        if isinstance(list_of_lines, list):

            with concurrent.futures.ProcessPoolExecutor(max_workers=AppConfig.jisho_multipro_max_workers) as executor:
                index_list = [index for index, line in enumerate(list_of_lines)]
                list_of_jisho_parsed_html_elements = list(
                    executor.map(Transmute.parse_string_with_jisho, list_of_lines, index_list))
                print(list_of_jisho_parsed_html_elements)
            logger.info("JISHO AutoParse: All lines parsed")

            # Replace Jisho relative ref urls with full urls and add classes to open jisho links in embedded iframe
            list_of_jisho_parsed_html_elements = [html.replace('/search/', 'https://jisho.org/search/')
                                                  for html in list_of_jisho_parsed_html_elements]

            list_of_jisho_parsed_html_elements = [html.replace('class="current"', 'class="||placeholder||"')
                                                  for html in list_of_jisho_parsed_html_elements]

            list_of_jisho_parsed_html_elements = [html.replace('class="||placeholder||"', 'class="jisho-link"')
                                                  for html in list_of_jisho_parsed_html_elements]

        else:
            logger.error(f"JISHO AUTOPARSE:Type ERROR: argument was not a list but {str(type(list_of_lines))}")
            raise TypeError(f"JISHO AutoParse: argument was not a list but {str(type(list_of_lines))}")

        return list_of_jisho_parsed_html_elements

    @staticmethod
    def translate_string_with_deepl_web(line: str, index: str = 0) -> str:

        """DOCSTRING PENDING"""

        driver = webdriver.Chrome()

        deepl_translated_text = str()

        if Classifier.contains_no_parsable_text(line):
            deepl_translated_text += 'un-parsable'

        else:
            logger.info(f'Trying to translate line {index}')

            driver.get(f'https://deepl.com/translator#ja/en/{line}')
            logger.info('Webdriver initiated')

            try:

                input_div_element = WebDriverWait(driver, 10).until(
                    ec.visibility_of_element_located(
                        (By.CSS_SELECTOR,
                         "div[contenteditable='true'][role='textbox'][aria-labelledby='translation-source-heading']")))

                # Clear input <div> from previous input
                input_div_element.clear()

                # Send the current sentence to be translated to DeepL
                input_div_element.send_keys(line)

                # logging
                logger.info(f'Input text sent: {line}')

                # Wait for output to be generated
                sleep(5)

                # Identify the output <div> using CSS tag
                output_div_element = WebDriverWait(driver, 10).until(
                    ec.visibility_of_element_located(
                        (By.CSS_SELECTOR,
                         "div[contenteditable='true'][role='textbox'][aria-labelledby='translation-target-heading']")))

                deepl_translated_text = output_div_element.find_element(By.TAG_NAME, "p").text

                logger.info(f'Translated text extracted: {deepl_translated_text}')

                deepl_translated_text = deepl_translated_text.strip()

                return deepl_translated_text

            except (NoSuchElementException, TimeoutException, Exception) as e:

                deepl_translated_text = f'Translation failed as {str(e)}'
                logger.error(f'{str(e)}')
                return deepl_translated_text

    @staticmethod
    def translate_list_with_deepl_web(list_of_lines: list) -> list:

        """DOCSTRING PENDING"""

        logger.info('DeepL web translator function initialized')

        if isinstance(list_of_lines, list):
            with concurrent.futures.ProcessPoolExecutor(max_workers=AppConfig.deepl_multipro_max_workers) as executor:
                index_list = [index for index, line in enumerate(list_of_lines)]
                list_of_deepl_translated_lines = list(
                    executor.map(Transmute.translate_string_with_deepl_web, list_of_lines, index_list))

            logger.info("All lines translated with DeepL web")

        else:
            logger.error(f"JISHO AUTOPARSE:Type ERROR: argument was not a list but {str(type(list_of_lines))}")
            raise TypeError(f"JISHO AutoParse: argument was not a list but {str(type(list_of_lines))}")

        return list_of_deepl_translated_lines

    @staticmethod
    def tts_string_with_google_api(line: str) -> list:

        """DOCSTRING PENDING"""

        # Get configration on run
        language_code: str = AppConfig.GoogleTTSConfig.language_code
        ssml_gender = AppConfig.GoogleTTSConfig.ssml_gender
        voice_name: str = AppConfig.GoogleTTSConfig.voice_name
        audio_encoding = AppConfig.GoogleTTSConfig.audio_encoding
        speaking_rate: float = AppConfig.GoogleTTSConfig.speaking_rate
        pitch: float = AppConfig.GoogleTTSConfig.pitch
        volume_gain_db: float = AppConfig.GoogleTTSConfig.volume_gain_db

        tts_client = texttospeech.TextToSpeechClient()
        input_for_synthesis = texttospeech.SynthesisInput({"text": f"{line}"})
        voice_settings = texttospeech.VoiceSelectionParams(
            {
                "language_code": language_code,
                "ssml_gender": ssml_gender,
                "name": voice_name
            }
        )
        audio_configuration = texttospeech.AudioConfig(
            {
                "audio_encoding": audio_encoding,
                "speaking_rate": speaking_rate,
                "pitch": pitch,
                "volume_gain_db": volume_gain_db,
            }
        )
        logger.info(f'TTS_API_CALL: Line: {line}')

        api_response = tts_client.synthesize_speech(
            input=input_for_synthesis,
            voice=voice_settings,
            audio_config=audio_configuration)

        logger.info(f'TTS_API_CALL for {line} was sucessful')
        output = [line, api_response.audio_content]
        return output

    @staticmethod
    def tts_list_with_google_api(list_of_lines: list) -> list[list[str | bytes]]:

        """DOCSTRING PENDING"""

        if isinstance(list_of_lines, list):
            with concurrent.futures.ProcessPoolExecutor(max_workers=AppConfig.tts_multipro_max_workers) as executor:
                output_list = list(executor.map(Transmute.tts_string_with_google_api, list_of_lines))
        return output_list


