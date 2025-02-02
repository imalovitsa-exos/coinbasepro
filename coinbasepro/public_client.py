import requests
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Iterator, List, Optional, Union

from coinbasepro.exceptions import (CoinbaseAPIError, BadRequest, InvalidAPIKey,
                                    InvalidAuthorization, RateLimitError)


class PublicClient(object):
    """Coinbase Pro public client API.

    All requests default to the `product_id` specified at object
    creation if not otherwise specified.

    Attributes:
        url (Optional[str]): API URL. Defaults to Coinbase Pro API.
        session (requests.Session): Persistent HTTP connection object.
        request_timeout (int): HTTP request timeout (in seconds).

    """

    def __init__(self,
                 api_url: str = 'https://api.pro.coinbase.com',
                 request_timeout: int = 30):
        """Creates a Coinbase Pro API public client instance.

        Args:
            api_url: API URL. Defaults to Coinbase Pro API.
            request_timeout: Request timeout (in seconds).

        """
        self.url = api_url.rstrip('/')
        self.auth = None  # No auth needed for public client
        self.session = requests.Session()
        self.request_timeout = request_timeout

    def get_products(self) -> List[Dict[str, Any]]:
        """Gets a list of available currency pairs for trading.

        The `base_min_size` and `base_max_size` fields define the min
        and max order size. The `quote_increment` field specifies the
        min order price as well as the price increment.

        The order price must be a multiple of this increment (i.e. if
        the increment is 0.01, order prices of 0.001 or 0.021 would be
        rejected).

        Returns:
            Info about all currency pairs. Example::
                [
                    {
                        'id': 'BTC-USD',
                        'display_name': 'BTC/USD',
                        'base_currency': 'BTC',
                        'quote_currency': 'USD',
                        'base_min_size': Decimal('0.001'),
                        'base_max_size': Decimal('70'),
                        'quote_increment': Decimal('0.01'),
                        'display_name': 'BTC/USD',
                        'status': 'online',
                        'margin_enabled': False,
                        'status_message': None,
                        'min_market_funds': 10,
                        'max_market_funds': 1000000,
                        'post_only': False,
                        'limit_only': False
                    }, {
                    ...
                    }
                ]

        Raises:
            coinbasepro.exceptions.BadRequest: Invalid API format
                 or parameters.
            coinbasepro.exceptions.InvalidAPIKey: Invalid API key.
            coinbasepro.exceptions.InvalidAuthorization: API key does
                not have sufficient authorization for action.
            coinbasepro.exceptions.RateLimitError: The API rate limit
                was exceeded.
            coinbasepro.exceptions.CoinbaseAPIError: Ambiguous Coinbase
                Pro error not covered by specific exceptions above.
                Additionally, parent of all above exceptions.

        """
        field_conversions = {'base_min_size': Decimal,
                             'base_max_size': Decimal,
                             'quote_increment': Decimal}
        r = self._send_message('get', '/products')
        return self._convert_list_of_dicts(r, field_conversions)

    def get_product_order_book(self, product_id: str, level: int = 1) -> Dict:
        """Gets a list of open orders for a product.

        The amount of detail shown can be customized with the `level`
        parameter:
        * 1: Only the best bid and ask
        * 2: Top 50 bids and asks (aggregated)
        * 3: Full order book (non aggregated)

        Level 1 and Level 2 are recommended for polling. For the most
        up-to-date data, consider using the websocket stream.

        **Caution**: Level 3 is only recommended for users wishing to
        maintain a full real-time order book using the websocket
        stream. Abuse of Level 3 via polling will cause your access to
        be limited or blocked.

        Args:
            product_id: Product.
            level: Order book level (1, 2, or 3). Default is 1.

        Returns:
            Order book. Example for level 1::
                {
                    'sequence': '3',
                    'bids': [
                        [price, size, num-orders],
                    ],
                    'asks': [
                        [price, size, num-orders],
                    ]
                }

        Raises:
            See `get_products()`.

        """
        params = {'level': level}
        return self._send_message('get',
                                  '/products/{}/book'.format(product_id),
                                  params=params)

    def get_product_ticker(self, product_id: str) -> Dict[str, Any]:
        """Snapshot about the last trade (tick), best bid/ask and 24h volume.

        **Caution**: Polling is discouraged in favor of connecting via
        the websocket stream and listening for match messages.

        Args:
            product_id: Product.

        Returns:
            Ticker info. Example::
                {
                  'trade_id': 4729088,
                  'price': Decimal('333.99'),
                  'size': Decimal('0.193'),
                  'bid': Decimal('333.98'),
                  'ask': Decimal('333.99'),
                  'volume': Decimal('5957.11914015'),
                  'time': datetime(2019, 3, 19, 22, 26, 27, 570000)
                }

        Raises:
            See `get_products()`.

        """
        field_conversions = {'trade_id': int,
                             'price': Decimal,
                             'size': Decimal,
                             'bid': Decimal,
                             'ask': Decimal,
                             'volume': Decimal,
                             'time': self._parse_datetime}
        r = self._send_message('get', '/products/{}/ticker'.format(product_id))
        return self._convert_dict(r, field_conversions)

    def get_product_trades(self, product_id: str) -> Iterator[Dict[str, Any]]:
        """Lists the latest trades for a product.

        This method returns a generator which may make multiple HTTP
        requests while iterating through it.

        Args:
            product_id: Product.

        Yields:
            Latest trades. Example::
                [{
                    'time': datetime(2019, 3, 19, 22, 26, 27, 570000),
                    'trade_id': 74,
                    'price': Decimal('10.00000000'),
                    'size': Decimal('0.01000000'),
                    'side': 'buy'
                }, {
                    'time': datetime(2019, 3, 19, 22, 26, 22, 520000),
                    'trade_id': 73,
                    'price': Decimal('100.00000000'),
                    'size': Decimal('0.01000000'),
                    'side': 'sell'
                }]

        Raises:
            See `get_products()`.

        """
        field_conversions = {'time': self._parse_datetime,
                             'trade_id': int,
                             'price': Decimal,
                             'size': Decimal}
        trades = self._send_paginated_message('/products/{}/trades'
                                              .format(product_id))
        return (self._convert_dict(trade, field_conversions)
                for trade in trades)

    def get_product_historic_rates(self,
                                   product_id: str,
                                   start: Optional[str] = None,
                                   stop: Optional[str] = None,
                                   granularity: Optional[str] = None
                                   ) -> List[Dict[str, Any]]:
        """Gets historic rates for a product.

        Rates are returned in grouped buckets based on requested
        `granularity`. If start, end, and granularity aren't provided,
        the exchange will provide the latest 300 ticks with 60s
        granularity (one minute).

        Historical rate data may be incomplete. No data is published
        for intervals where there are no ticks.

        **Caution**: Historical rates should not be polled frequently.
        If you need real-time information, use the trade and book
        endpoints along with the websocket feed.

        The maximum number of data points for a single request is 300
        candles. If your selection of start/end time and granularity
        will result in more than 300 data points, your request will be
        rejected. If you wish to retrieve fine granularity data over a
        larger time range, you will need to make multiple requests with
        new start/end ranges.

        Args:
            product_id: Product.
            start: Start time in ISO 8601.
            stop: End time in ISO 8601.
            granularity: Desired time slice in seconds.

        Returns:
            Historic candle data. Example::
                [{
                    'time': datetime(2019, 3, 19, 22, 26, 22, 520000),
                    'low': Decimal('0.32'),
                    'high': Decimal('4.2'),
                    'open': Decimal('0.35'),
                    'close': Decimal('4.2'),
                    'volume': Decimal('12.3')
                },
                    ...
                ]

        Raises:
            See `get_products()`.

        """
        def convert_candle(c):
            out = dict()
            out['time'] = datetime.utcfromtimestamp(c[0])
            out['low'] = c[1]
            out['high'] = c[2]
            out['open'] = c[3]
            out['close'] = c[4]
            out['volume'] = c[5]
            return out

        params = {}
        if start is not None:
            params['start'] = start
        if stop is not None:
            params['end'] = stop
        if granularity is not None:
            params['granularity'] = granularity

        candles = self._send_message('get',
                                     '/products/{}/candles'.format(product_id),
                                     params=params)
        return [convert_candle(c) for c in candles]

    def get_product_24hr_stats(self, product_id: str) -> Dict[str, Any]:
        """Gets 24 hr stats for the product.

        Args:
            product_id: Product.

        Returns:
            24 hour stats. Volume is in base currency units.
                Open, high, low are in quote currency units. Example::
                    {
                        'open': Decimal('3961.34000000'),
                        'high': Decimal('4017.49000000'),
                        'low': Decimal('3954.63000000'),
                        'volume': Decimal('6249.19597605'),
                        'last': Decimal('3980.52000000'),
                        'volume_30day': Decimal('238421.35846878')
                    }

        Raises:
            See `get_products()`.

        """
        field_conversions = {'open': Decimal,
                             'high': Decimal,
                             'low': Decimal,
                             'volume': Decimal,
                             'last': Decimal,
                             'volume_30day': Decimal}
        stats = self._send_message('get', '/products/{}/stats'
                                   .format(product_id))
        return self._convert_dict(stats, field_conversions)

    def get_currencies(self) -> List[Dict[str, Any]]:
        """Lists known currencies.

        Returns:
            List of currencies. Example::
                [{
                    'id': 'BTC',
                    'name': 'Bitcoin',
                    'min_size': Decimal('0.00000001'),
                    'status': 'online',
                    'message': None,
                    'details': {
                        'type': 'crypto',
                        'symbol': '\u20bf',
                        'network_confirmations': 6,
                        'sort_order': 3,
                        'crypto_address_link': 'https://live.blockcypher.com/btc/address/{{address}}',
                        'crypto_transaction_link': 'https://live.blockcypher.com/btc/tx/{{txId}}',
                        'push_payment_methods': ['crypto']
                    }

                }, {
                    'id': 'EUR',
                    'name': 'Euro',
                    'min_size': Decimal('0.01000000'),
                    'status': 'online',
                    'message': None,
                    'details': {
                        'type': 'fiat',
                        'symbol': '€',
                        'sort_order': 1,
                        'push_payment_methods': ['sepa_bank_account']
                    }
                }]

        Raises:
            See `get_products()`.

        """
        field_conversions = {'min_size': Decimal}
        currencies = self._send_message('get', '/currencies')
        return self._convert_list_of_dicts(currencies, field_conversions)

    def get_time(self) -> Dict[str, Any]:
        """Gets the API server time.

        Returns:
            Server time in ISO and epoch format (decimal seconds since
            Unix epoch). Example::
                    {
                        'iso': datetime(2019, 3, 19, 22, 26, 22, 520000),
                        'epoch': 1420674445.201
                    }

        Raises:
            See `get_products()`.

        """
        field_conversions = {'iso': self._parse_datetime}
        times = self._send_message('get', '/time')
        return self._convert_dict(times, field_conversions)

    @staticmethod
    def _check_errors_and_raise(response):
        """Check for error codes and raise an exception if necessary."""
        if 400 <= response.status_code < 600:
            message = response.json()['message']
            if response.status_code == 400:
                raise BadRequest(message)
            elif response.status_code == 401:
                raise InvalidAPIKey(message)
            elif response.status_code == 403:
                raise InvalidAuthorization(message)
            elif response.status_code == 429:
                raise RateLimitError(message)
            else:
                raise CoinbaseAPIError(message)

    def _send_message(self,
                      method: str,
                      endpoint: str,
                      params: Optional[Dict] = None,
                      data: Optional[str] = None) -> Union[List, Dict]:
        """Sends API request.

        Args:
            method: HTTP method (get, post, delete, etc.)
            endpoint: Endpoint (to be added to base URL)
            params: HTTP request parameters
            data: JSON-encoded string payload for POST

        Returns:
            JSON response

        Raises:
            See `get_products()`.

        """
        url = self.url + endpoint
        r = self.session.request(method,
                                 url,
                                 params=params,
                                 data=data,
                                 auth=self.auth,
                                 timeout=self.request_timeout)
        self._check_errors_and_raise(r)
        return r.json(parse_float=Decimal)

    def _send_paginated_message(self,
                                endpoint: str,
                                params: Optional[Dict] = None
                                ) -> Iterator[Dict]:
        """Sends API message that results in a paginated response.

        The paginated responses are abstracted away by making API
        requests on demand as the response is iterated over.

        Paginated API messages support 3 additional parameters:
        `before`, `after`, and `limit`. `before` and `after` are
        mutually exclusive. To use them, supply an index value for that
        endpoint (the field used for indexing varies by endpoint -
        get_fills() uses 'trade_id', for example).

        `before`: Only get data that occurs more recently than index.
        `after`: Only get data that occurs further in the past than
            index.
        `limit`: Set amount of data per HTTP response. Default (and
            maximum) of 100.

        Args:
            endpoint: Endpoint (to be added to base URL)
            params: HTTP request parameters

        Yields:
            API response objects

        Raises:
            See `get_products()`.

        """
        if params is None:
            params = dict()
        url = self.url + endpoint
        while True:
            r = self.session.get(url,
                                 params=params,
                                 auth=self.auth,
                                 timeout=self.request_timeout)
            self._check_errors_and_raise(r)
            results = r.json(parse_float=Decimal)
            for result in results:
                yield result
            # If there are no more pages, we're done. Otherwise update `after`
            # param to get next page.
            # If this request included `before` don't get any more pages - the
            # Coinbase pro API doesn't support multiple pages in that case.
            if not r.headers.get('cb-after') or \
                    params.get('before') is not None:
                break
            else:
                params['after'] = r.headers['cb-after']

    @staticmethod
    def _parse_datetime(dt):
        try:
            return datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError:
            return datetime.strptime(dt, '%Y-%m-%dT%H:%M:%SZ')

    @staticmethod
    def _convert_dict(r, field_conversions):
        for field, converter in field_conversions.items():
            if field in r:
                r[field] = converter(r[field])
        return r

    @staticmethod
    def _convert_list(r, field_conversions):
        return [conversion(x) for x, conversion in zip(r, field_conversions)]

    @classmethod
    def _convert_list_of_dicts(cls, r, field_conversions):
        return [cls._convert_dict(x, field_conversions) for x in r]
