# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2017-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE URL <https://store.webkul.com/license.html/> for full copyright and licensing details.
#################################################################################
ListOrders="""<?xml version="1.0"?>
<ListOrdersResponse xmlns="https://mws.amazonservices.com/
    Orders/2013-09-01">
    <ListOrdersResult>
        <NextToken>2YgYW55IGNhcm5hbCBwbGVhc3VyZS4=</NextToken>
        <LastUpdatedBefore>2013-09-25T18%3A10%3A21.687Z</LastUpdatedBefore>
        <Orders>
            <Order>
                <ShipmentServiceLevelCategory>Standard
                </ShipmentServiceLevelCategory>
                <ShipServiceLevel>Std JP Kanto8</ShipServiceLevel>
                <EarliestShipDate>2013-08-20T19:51:16Z</EarliestShipDate>
                <LatestShipDate>2013-08-25T19:49:35Z</LatestShipDate>	
                <MarketplaceId>A1VC38T7YXB528</MarketplaceId>
                <SalesChannel>Amazon.com</SalesChannel>
                <OrderType>Preorder</OrderType>
                <BuyerEmail>5vlhEXAMPLEh9h5@marketplace.amazon.com</BuyerEmail>
                <FulfillmentChannel>MFN</FulfillmentChannel>
                <OrderStatus>Pending</OrderStatus>
                <BuyerName>John Jones</BuyerName>	
                <LastUpdateDate>2013-08-20T19:49:35Z</LastUpdateDate>
                <PurchaseDate>2013-08-20T19:49:35Z</PurchaseDate>
                <NumberOfItemsShipped>0</NumberOfItemsShipped>
                <NumberOfItemsUnshipped>0</NumberOfItemsUnshipped>
                <AmazonOrderId>902-3159896-1390916</AmazonOrderId>
                <PaymentMethod>Other</PaymentMethod>
                <IsBusinessOrder>true</IsBusinessOrder>
                <PurchaseOrderNumber>PO12345678</PurchaseOrderNumber>
                <IsPrime>false</IsPrime>
                <IsPremiumOrder>false</IsPremiumOrder>
            </Order>
            <Order>
                <AmazonOrderId>058-1233752-8214740</AmazonOrderId>
                <PurchaseDate>2013-09-05T00%3A06%3A07.000Z</PurchaseDate>      
                <LastUpdateDate>2013-09-07T12%3A43%3A16.000Z</LastUpdateDate>
                <OrderStatus>Unshipped</OrderStatus>
                <OrderType>StandardOrder</OrderType>
                <ShipServiceLevel>Std JP Kanto8</ShipServiceLevel>
                <FulfillmentChannel>MFN</FulfillmentChannel>
                <OrderTotal>
                    <CurrencyCode>JPY</CurrencyCode>
                    <Amount>1507.00</Amount>
                </OrderTotal>
                <ShippingAddress>
                    <Name>Jane Smith</Name>
                    <AddressLine1>1-2-10 Akasaka</AddressLine1>
                    <City>Tokyo</City>
                    <PostalCode>107-0053</PostalCode>
                    <CountryCode>JP</CountryCode>
                </ShippingAddress>
                <NumberOfItemsShipped>0</NumberOfItemsShipped>
                <NumberOfItemsUnshipped>1</NumberOfItemsUnshipped>
                <PaymentExecutionDetail>
                    <PaymentExecutionDetailItem>
                        <Payment>
                            <Amount>10.00</Amount>
                            <CurrencyCode>JPY</CurrencyCode>
                        </Payment>
                        <PaymentMethod>PointsAccount</PaymentMethod>
                    </PaymentExecutionDetailItem>
                    <PaymentExecutionDetailItem>
                        <Payment>
                            <Amount>317.00</Amount>
                            <CurrencyCode>JPY</CurrencyCode>
                        </Payment>
                        <PaymentMethod>GC</PaymentMethod>
                    </PaymentExecutionDetailItem>
                    <PaymentExecutionDetailItem>
                        <Payment>
                            <Amount>1180.00</Amount>
                            <CurrencyCode>JPY</CurrencyCode>
                        </Payment>
                        <PaymentMethod>COD</PaymentMethod>
                    </PaymentExecutionDetailItem>
                </PaymentExecutionDetail>
                <PaymentMethod>COD</PaymentMethod>
                <MarketplaceId>ATVPDKIKX0DER</MarketplaceId>
                <BuyerName>Jane Smith</BuyerName>
                <BuyerEmail>5vlhEXAMPLEh9h5@marketplace.amazon.com</BuyerEmail>
                <ShipmentServiceLevelCategory>Standard
                </ShipmentServiceLevelCategory>
                <IsBusinessOrder>false</IsBusinessOrder>
                <IsPrime>false</IsPrime>
                <IsPremiumOrder>false</IsPremiumOrder>
            </Order>
        </Orders>
    </ListOrdersResult>
    <ResponseMetadata>
        <RequestId>88faca76-b600-46d2-b53c-0c8c4533e43a</RequestId>
    </ResponseMetadata>
</ListOrdersResponse>""" 

GetOrder = """<?xml version="1.0"?>
<GetOrderResponse xmlns="https://mws.amazonservices.com/
    Orders/2013-09-01">
    <GetOrderResult>
        <NextToken>2YgYW55IGNhcm5hbCBwbGVhc3VyZS4=</NextToken>
        <LastUpdatedBefore>2013-09-25T18%3A10%3A21.687Z</LastUpdatedBefore>
        <Orders>
            <Order>
                <AmazonOrderId>058-1233752-8214740</AmazonOrderId>
                <PurchaseDate>2013-09-05T00%3A06%3A07.000Z</PurchaseDate>      
                <LastUpdateDate>2013-09-07T12%3A43%3A16.000Z</LastUpdateDate>
                <OrderStatus>Unshipped</OrderStatus>
                <OrderType>StandardOrder</OrderType>
                <ShipServiceLevel>Std JP Kanto8</ShipServiceLevel>
                <FulfillmentChannel>MFN</FulfillmentChannel>
                <OrderTotal>
                    <CurrencyCode>JPY</CurrencyCode>
                    <Amount>1507.00</Amount>
                </OrderTotal>
                <ShippingAddress>
                    <Name>Jane Smith</Name>
                    <AddressLine1>1-2-10 Akasaka</AddressLine1>
                    <City>Tokyo</City>
                    <PostalCode>107-0053</PostalCode>
                    <CountryCode>JP</CountryCode>
                </ShippingAddress>
                <NumberOfItemsShipped>0</NumberOfItemsShipped>
                <NumberOfItemsUnshipped>1</NumberOfItemsUnshipped>
                <PaymentExecutionDetail>
                    <PaymentExecutionDetailItem>
                        <Payment>
                            <Amount>10.00</Amount>
                            <CurrencyCode>JPY</CurrencyCode>
                        </Payment>
                        <PaymentMethod>PointsAccount</PaymentMethod>
                    </PaymentExecutionDetailItem>
                    <PaymentExecutionDetailItem>
                        <Payment>
                            <Amount>317.00</Amount>
                            <CurrencyCode>JPY</CurrencyCode>
                        </Payment>
                        <PaymentMethod>GC</PaymentMethod>
                    </PaymentExecutionDetailItem>
                    <PaymentExecutionDetailItem>
                        <Payment>
                            <Amount>1180.00</Amount>
                            <CurrencyCode>JPY</CurrencyCode>
                        </Payment>
                        <PaymentMethod>COD</PaymentMethod>
                    </PaymentExecutionDetailItem>
                </PaymentExecutionDetail>
                <PaymentMethod>COD</PaymentMethod>
                <MarketplaceId>ATVPDKIKX0DER</MarketplaceId>
                <BuyerName>Jane Smith</BuyerName>
                <BuyerEmail>5vlhEXAMPLEh9h5@marketplace.amazon.com</BuyerEmail>
                <ShipmentServiceLevelCategory>Standard
                </ShipmentServiceLevelCategory>
                <IsBusinessOrder>false</IsBusinessOrder>
                <IsPrime>false</IsPrime>
                <IsPremiumOrder>false</IsPremiumOrder>          
            </Order>
        </Orders>
    </GetOrderResult>
    <ResponseMetadata>
        <RequestId>88faca76-b600-46d2-b53c-0c8c4533e43a</RequestId>
    </ResponseMetadata>
</GetOrderResponse>"""
ListOrderItems = """<?xml version="1.0"?>
<ListOrderItemsResponse xmlns="https://mws.amazonservices.com
    /Orders/2013-09-01">
    <ListOrderItemsResult>
        <NextToken>MRgZW55IGNhcm5hbCBwbGVhc3VyZS6=</NextToken>
        <AmazonOrderId>058-1233752-8214740</AmazonOrderId>
        <OrderItems>
            <OrderItem>
                <ASIN>BT0093TELA</ASIN>
                <OrderItemId>68828574383266</OrderItemId>
                <BuyerCustomizedInfo>
                    <CustomizedURL>https://zme-caps.amazon.com/t/bR6qHkzSOxuB/
                        J8nbWhze0Bd3DkajkOdY-XQbWkFralegp2sr_QZiKEE/1</CustomizedURL>
                </BuyerCustomizedInfo>
                <SellerSKU>CBA_OTF_1</SellerSKU>
                <Title>Example item name</Title>
                <QuantityOrdered>5</QuantityOrdered>
                <QuantityShipped>1</QuantityShipped>
                <PointsGranted>
                    <PointsNumber>10</PointsNumber>
                    <PointsMonetaryValue>
                        <CurrencyCode>JPY</CurrencyCode>
                        <Amount>10.00</Amount>
                    </PointsMonetaryValue>
                </PointsGranted>
                <ItemPrice>
                    <CurrencyCode>JPY</CurrencyCode>
                    <Amount>25.99</Amount>
                </ItemPrice>
                <ShippingPrice>
                    <CurrencyCode>JPY</CurrencyCode>
                    <Amount>1.26</Amount>
                </ShippingPrice>
                <ScheduledDeliveryEndDate>2013-09-09T01:30:00.000-06:00
                </ScheduledDeliveryEndDate>
                <ScheduledDeliveryStartDate>2013-09-071T02:00:00.000-06:00
                </ScheduledDeliveryStartDate>
                <CODFee>
                    <CurrencyCode>JPY</CurrencyCode>
                    <Amount>10.00</Amount>
                </CODFee>
                <CODFeeDiscount>
                    <CurrencyCode>JPY</CurrencyCode>
                    <Amount>1.00</Amount>
                </CODFeeDiscount>   
                <GiftMessageText>For you!</GiftMessageText>
                <GiftWrapPrice>
                    <CurrencyCode>JPY</CurrencyCode>
                    <Amount>1.99</Amount>
                </GiftWrapPrice>
                <GiftWrapLevel>Classic</GiftWrapLevel>
                <PriceDesignation>BusinessPrice</PriceDesignation>
            </OrderItem>
            <OrderItem>
                <ASIN>BCTU1104UEFB</ASIN>
                <OrderItemId>79039765272157</OrderItemId>
                <SellerSKU>CBA_OTF_5</SellerSKU>
                <Title>Example item name</Title>
                <QuantityOrdered>2</QuantityOrdered>
                <ItemPrice>
                    <CurrencyCode>JPY</CurrencyCode>
                    <Amount>17.95</Amount>
                </ItemPrice>
                <PromotionIds>
                    <PromotionId>FREESHIP</PromotionId>
                </PromotionIds>
                <ConditionId>Used</ConditionId>
                <ConditionSubtypeId>Mint</ConditionSubtypeId>
                <ConditionNote>Example ConditionNote</ConditionNote>
                <PriceDesignation>BusinessPrice</PriceDesignation>
            </OrderItem>
        </OrderItems>
    </ListOrderItemsResult>
    <ResponseMetadata>
        <RequestId>88faca76-b600-46d2-b53c-0c8c4533e43a</RequestId>
    </ResponseMetadata>
</ListOrderItemsResponse>"""