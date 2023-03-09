import scrapy
import json
from kscrap.items import KscrapItem


class TestSpider(scrapy.Spider):
    name = "main_spider"
    API_URL = "https://website.com/api/items"
    PRODUCT_URL = "https://website.com/api/items/{0}/"
    MAX_PROUDCT_PER_CATE = 600
    show_exist = False
    cate_url = [
        {
            "cate_name": "testname",
            "cate_code": "testcode",
            "ul_li_index": 3,
            "subdomain": "subdomain",
        },
        {
            "cate_name": "testname",
            "cate_code": "testcode",
            "ul_li_index": 3,
            "subdomain": "subdomain",
        },
    ]

    def __init__(self, show_exist=False, **kwargs):
        self.show_exist = show_exist
        super().__init__(**kwargs)

    def start_requests(self):
        # GET request
        for i in self.cate_url:
            data = {
                # data
            }
            yield scrapy.Request(
                url=self.API_URL,
                method="POST",
                body=json.dumps(data),
                headers={"Content-Type": "application/json"},
                cb_kwargs={
                    "cate_name": i["cate_name"],
                    "tilte_ul": str(i["ul_li_index"]),
                    "subdomain": i["subdomain"],
                },
            )

    def parse_items(self, response, **kwargs):

        url = response.url
        Published = "1"
        if response is None:
            return
        try:
            cate = (
                response.xpath(
                    '//*[@id="id"]/ul/li[{0}]/a/span/text()'.format(
                        kwargs["tilte_ul"]
                    )
                )
                .get()
                .replace("قیمت", "")
            )
        except:
            cate = ""
        if "cate_name" in kwargs:
            category = "{0} > {1},{0}".format(kwargs["cate_name"], cate)
        else:
            category = "{0}".format(cate)

        persian_name = response.xpath("//*[@id='id']/text()").get()
        # english_name = response.xpath("//*[@id='splitname']//text()").get()
        available = response.xpath('//*[@id="id"]/span/text()').get()
        price = response.xpath(
            '//*[@id="id"]/div[2]/div[2]/span[1]/text()'
        ).get()
        image = response.urljoin(
            response.xpath('//*[@id="img_product"]/img/@src').get()
        )

        item = KscrapItem()
        if persian_name is None:
            assert "persian name is none"
        else:
            item["Name"] = persian_name.strip()
        if response.xpath('//*[@id="id"]/span/text()').get():
            item["In_stock"] = "0"
        else:
            item["In_stock"] = "1"

        if (
            response.urljoin(response.xpath('//*[@id="id"]/img/@src').get())
            == "https://website.com/img/default.jpg"
        ):
            item[
                "Images"
            ] = "https://wordpress.ir/wp-content/uploads/600x600.png"
        else:
            item["Images"] = image

        item["Regular_price"] = price.strip()
        item["Categories"] = category
        item["Published"] = Published

        item_id = response.url.split("/")
        item_id = item_id[len(item_id) - 1]
        item["SKU"] = item_id
        my_data = {"itemid": item_id}
        request = scrapy.Request(
            "https://website.com/api/items/comments",
            method="POST",
            body=json.dumps(my_data),
            headers={"Content-Type": "application/json"},
            callback=self.pars_details,
        )
        # add more arguments for the callback
        request.cb_kwargs["items"] = item
        yield request

    def parse(self, response, **kwargs):
        data = json.loads(response.body)
        for i in data["goods"]:
            yield scrapy.Request(
                self.PRODUCT_URL.format(kwargs["subdomain"]) + str(i["itemid"]),
                callback=self.parse_items,
                cb_kwargs=kwargs,
            )

    def pars_details(self, response, **kwargs):
        api_res = str(response.body.decode("utf-8")).replace("\n", "")
        api_res = api_res.replace("\r", "")
        api_res = api_res[0 : api_res.index("_items") - 2] + "}"
        data = json.loads(api_res)
        kwargs["items"]
        kwargs["items"]["Short_description"] = ""
        kwargs["items"]["Description"] = ""
        for i in data["_propertyJson"]["Labels"]:
            kwargs["items"]["Short_description"] += "{0}:{1}{2}".format(
                i["PropertyName"], i["PropertyValue"], "\n"
            )
        for i in data["_propertyJson"]["Properties"]:
            kwargs["items"]["Description"] += "{0}:{1}{2}".format(
                i["Name"], i["Value"][0]["ValueText"], "\n"
            )
        return kwargs["items"]