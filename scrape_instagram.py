import hashlib
import re
import time
import urllib2
from datetime import datetime
from selenium import webdriver


TIME_SLEEP = 1  # Second
TIME_IMPLICIT_WAIT_LONG = 10  # Second
TIME_IMPLICIT_WAIT_SHORT = 0.5 # Second

BUFFER_SIZE = 8192  # byte
ITEMS_PER_PAGE = 20


class FileDownloader:
    """ Manage download jobs
    Attributes:
        job_id: job ID
        jobs_todo: unfinished jobs
        jobs_done: finished jobs
    """

    def __init__(self, jobs_todo, jobs_done=None):
        self.job_id = hashlib.sha224(str(datetime.now())).hexdigest()
        self.jobs_todo = jobs_todo
        self.jobs_done = jobs_done

    @staticmethod
    def download_resource(resource_url):
        """
        Download the resource files
        :param resource_url:
        :return
        """
        file_name = resource_url.split('/')[-1]
        try:
            download_url = urllib2.urlopen(resource_url)
            fd = open(file_name, 'wb')
        except IOError as e:
            raise IOError

        meta = download_url.info()
        file_size = int(meta.getheaders("Content-Length")[0])
        print "Downloading: %s Bytes: %s" % (file_name, file_size)

        file_size_dl = 0
        block_sz = BUFFER_SIZE
        while True:
            file_buffer = download_url.read(block_sz)
            if not file_buffer:
                break
            file_size_dl += len(file_buffer)
            fd.write(file_buffer)
            status = r"%10d  [%3.2f%%]" % (file_size_dl, file_size_dl * 100. / file_size)
            status += chr(8) * (len(status) + 1)
            print status,
        fd.close()

    def batch_downloader(self):
        """
        Download files in batch
        :return:
        """
        for job_url in self.jobs_todo:
            try:
                FileDownloader.download_resource(job_url)
                time.sleep(TIME_SLEEP)
                self.jobs_todo.remove(job_url)
                self.jobs_done.append(job_url)
            except IOError as e:
                print "File download failed {0}: {1} ".format(e.errno, e.strerror)

    def load_jobs(self, file_path):
        """
        Load download jobs from file
        :param file_path:
        :return:
        """
        self.clear_jobs()
        with open(file_path) as fd:
            fd.readline()
            for i in xrange(0, fd.read()):
                self.jobs_todo.append(fd.read())

            fd.readline()
            for i in xrange(0, fd.read()):
                self.jobs_done.append(fd.read())

            self.job_id = fd.read()

    def save_job(self, file_path):
        """
        Save jobs to file
        :param file_path:
        :return:
        """
        with open(file_path, 'w') as fd:
            fd.write("Jobs to do:\n")
            fd.write(str(len(self.jobs_todo)) + "\n")
            for job in self.jobs_todo:
                fd.write(str(job) + '\n')

            fd.write("Jobs done\n")
            fd.write(str(len(self.jobs_done)) + "\n")
            for job in self.jobs_done:
                fd.write(str(job) + '\n')

            fd.write(self.job_id)

        self.clear_jobs()

    def update_job(self, new_jobs):
        """
        Update todo job list
        :return:
        """
        total_jobs = self.jobs_todo + self.jobs_done
        for element in new_jobs:
            if element not in total_jobs:
                self.jobs_todo.append(element)

    def clear_jobs(self):
        """
        Clear jobs
        :return:
        """
        self.jobs_todo = []
        self.jobs_done = []
        self.job_id = -1


class ScrapeInstagram:
    """ Download media files from Instagram.com

    Selenium Webdriver is required to mimic the browser action.
    The webdriver clicks "Load more" button in the main page (e.g.:
    https://instagram.com/i_love_cats/) to trigger new ajax requests
    and the urls of each thumbnail are grepped to a list. Then each
    thumbnail url is open to get the resource urls.

    Attributes:
        driver: Selenium webdriver instance
        resource_urls: resource urls
    """

    def __init__(self):
        self.driver = webdriver.Chrome()
        self.resource_urls = []

    def __del__(self):
        self.driver.close()

    def scrape_thumbnail_links(self, user_url, max_items):
        """
        Get thumbnail_links
        :param user_url: instagram user root page
        :param max_items: maximum number of files to download
        :return: thumbnail_links
        """
        self.driver.implicitly_wait(TIME_IMPLICIT_WAIT_LONG)
        self.driver.get(user_url)

        thumbnail_links = []
        load_more = re.compile(r"^Load(ing)? more.*")

        thumbnail_count = 0
        while load_more.match(self.driver.find_element_by_class_name(
                              'PhotoGridMoreButton').text):
            thumbnail_count += ITEMS_PER_PAGE
            if thumbnail_count >= max_items:
                break
            (self.driver.find_element_by_class_name("PhotoGridMoreButton")
                .click())
            time.sleep(TIME_SLEEP * 3)
            #self.driver.execute_script(
            #    "javascript:window.scrollTo(0,document.body.scrollHeight);")

        # where the thumbnail link hides
        for link in self.driver.find_elements_by_class_name('pgmiImageLink'):
            thumbnail_links.append(link.get_attribute('href'))

        return thumbnail_links[0:max_items]

    def scrape_resource_urls(self, thumbnail_links):
        """
        Get resource urls from the page which thumbnail urls point to
        :param thumbnail_links: thumbnail_links
        :return
        """
        self.driver.implicitly_wait(TIME_IMPLICIT_WAIT_SHORT)
        # cannot get attribute by webdriver API, parsing html instead
        picture_pattern = re.compile(r'(https://(?:(?!https).)*\.jpg)')
        video_pattern = re.compile(r'(https://(?:(?!https).)*\.mp4)')

        for link in thumbnail_links:
            self.driver.get(link)
            time.sleep(TIME_SLEEP / 2)
            root_element = self.driver.find_element_by_class_name("root")
            html = root_element.get_attribute("innerHTML")
            if isinstance(html, unicode):
                html = re.sub(r'[^\x00-\x7F]', ' ', html)
            dup = set()
            video_url = re.findall(video_pattern, html)
            picture_url = re.findall(picture_pattern, html)
            if video_url:
                dup |= set(video_url)
            dup.add(picture_url[0])  # Ignore the user profile pictures

            self.resource_urls += list(dup)

    def create_jobs(self):
        """
        Create a new job downloader
        :return:
        """
        return FileDownloader(list(set(self.resource_urls)), [])

    # TODO (Y. Z.): Support master-slave work mode
    # fetch thumbnail urls from main page while fetching url resource
    # and downloading files

    # TODO (Y. Z): Support browser action script
    # so that the code can be applied to other ajax websites


if __name__ == "__main__":
    scrape = ScrapeInstagram()
    thumbnail_links = scrape.scrape_thumbnail_links("https://instagram.com/apollinarya/", 10)
    print len(thumbnail_links)
    scrape.scrape_resource_urls(thumbnail_links)
    #scrape.resource_urls = [
    #    "https://igcdn-photos-c-a.akamaihd.net/hphotos-ak-xaf1/t51.2885-15/11024184_585392644931530_1380709261_n.jpg"]
    downloader = scrape.create_jobs()
    downloader.save_job("job.txt")

    #scrape.batch_downloader()



