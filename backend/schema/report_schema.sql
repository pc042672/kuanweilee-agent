--
-- Greenplum Database database dump
--

SET gp_default_storage_options = '';
SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;

--
-- Name: report; Type: SCHEMA; Schema: -; Owner: gpadmin
--

CREATE SCHEMA report;


ALTER SCHEMA report OWNER TO gpadmin;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: aroo_coupon; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.aroo_coupon (
    "交易日期" character varying,
    "交易序號" character varying,
    "買家姓名" character varying,
    "訂單編號" character varying,
    "商品編號" character varying,
    "商品名稱" character varying,
    "樣式" character varying,
    "尺寸" character varying,
    "訂單狀態" character varying,
    "訂單金額" character varying,
    "折扣金額" character varying,
    "運費" character varying,
    "交易小計" character varying,
    "折價券折扣金額" character varying,
    "折價券編號" character varying,
    "銷售成本" character varying,
    amount numeric,
    created_date date,
    tx_id character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.aroo_coupon OWNER TO gpadmin;

--
-- Name: aroo_daily_item; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.aroo_daily_item (
    search_id character varying,
    created_time date,
    total_quantity integer
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.aroo_daily_item OWNER TO gpadmin;

--
-- Name: aroo_item; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.aroo_item (
    "交易序號" character varying,
    "買家姓名" character varying,
    "訂單編號" character varying,
    "商品編號" character varying,
    "商品名稱" character varying,
    "樣式" character varying,
    "尺寸" character varying,
    "訂單狀態" character varying,
    "訂單金額" character varying,
    "折扣金額" character varying,
    "運費" character varying,
    "交易小計" character varying,
    "折價券折扣金額" character varying,
    "折價券編號" character varying,
    "銷售成本" character varying,
    amount numeric,
    created_time date,
    "﻿id" character varying,
    title character varying,
    description character varying,
    link character varying,
    image_link character varying,
    condition character varying,
    availability character varying,
    price character varying,
    sale_price character varying,
    brand character varying,
    google_product_category character varying,
    product_type character varying,
    uid character varying,
    "帳號類型" character varying,
    "會員帳號" character varying,
    "姓名" character varying,
    "電話" character varying,
    "地址" character varying,
    "EMAIL" character varying,
    "驗證電話" character varying,
    "年齡" character varying,
    "生日" character varying,
    "購物金" character varying,
    "紅利點數" character varying,
    "交易總金額" character varying,
    "交易總次數" character varying,
    "交易金額-USHOP1號店" character varying,
    "交易次數-USHOP1號店" character varying,
    "交易金額-USHOP0號店" character varying,
    "交易次數-USHOP0號店" character varying,
    "會員等級" character varying,
    "會員資格變更日" character varying,
    "會員資格到期日" character varying,
    "黑名單" character varying,
    "黑名單生效日" character varying,
    "赦免帳號" character varying,
    "接收電子報" character varying,
    "建立時間" character varying,
    "上次登入時間" character varying,
    "上次交易時間" character varying,
    "會員備註" character varying,
    year_old_range character varying,
    city character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.aroo_item OWNER TO gpadmin;

--
-- Name: aroo_item_old_error; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.aroo_item_old_error (
    "交易序號" character varying,
    "買家姓名" character varying,
    "訂單編號" character varying,
    "商品編號" character varying,
    "商品名稱" character varying,
    "樣式" character varying,
    "尺寸" character varying,
    "訂單狀態" character varying,
    "訂單金額" character varying,
    "折扣金額" character varying,
    "運費" character varying,
    "交易小計" character varying,
    "折價券折扣金額" character varying,
    "折價券編號" character varying,
    "銷售成本" character varying,
    amount numeric,
    created_time date,
    "﻿id" character varying,
    title character varying,
    description character varying,
    link character varying,
    image_link character varying,
    condition character varying,
    availability character varying,
    price character varying,
    sale_price character varying,
    brand character varying,
    google_product_category character varying,
    product_type character varying,
    "帳號類型" character varying,
    "會員帳號" character varying,
    "姓名" character varying,
    "電話" character varying,
    "地址" character varying,
    "EMAIL" character varying,
    "驗證電話" character varying,
    "年齡" character varying,
    "生日" character varying,
    "購物金" character varying,
    "紅利點數" character varying,
    "交易總金額" character varying,
    "交易總次數" character varying,
    "交易金額-USHOP1號店" character varying,
    "交易次數-USHOP1號店" character varying,
    "交易金額-USHOP0號店" character varying,
    "交易次數-USHOP0號店" character varying,
    "會員等級" character varying,
    "會員資格變更日" character varying,
    "會員資格到期日" character varying,
    "黑名單" character varying,
    "黑名單生效日" character varying,
    "赦免帳號" character varying,
    "接收電子報" character varying,
    "建立時間" character varying,
    "上次登入時間" character varying,
    "上次交易時間" character varying,
    "會員備註" character varying,
    year_old_range character varying,
    city character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.aroo_item_old_error OWNER TO gpadmin;

--
-- Name: aroo_item_zh; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.aroo_item_zh (
    "交易序號" character varying,
    "買家姓名" character varying,
    "樣式" character varying,
    "尺寸" character varying,
    "訂單狀態" character varying,
    "訂單金額" character varying,
    "折扣金額" character varying,
    "運費" character varying,
    "交易小計" character varying,
    "折價券編號" character varying,
    "銷售成本" character varying,
    amount numeric,
    created_time date,
    "﻿id" character varying,
    title character varying,
    description character varying,
    link character varying,
    image_link character varying,
    condition character varying,
    availability character varying,
    price character varying,
    sale_price character varying,
    brand character varying,
    google_product_category character varying,
    product_type character varying,
    "帳號類型" character varying,
    "會員帳號" character varying,
    "姓名" character varying,
    "電話" character varying,
    "地址" character varying,
    "EMAIL" character varying,
    "驗證電話" character varying,
    "年齡" character varying,
    "生日" character varying,
    "購物金" character varying,
    "紅利點數" character varying,
    "交易總金額" character varying,
    "交易總次數" character varying,
    "交易金額-USHOP1號店" character varying,
    "交易次數-USHOP1號店" character varying,
    "交易金額-USHOP0號店" character varying,
    "交易次數-USHOP0號店" character varying,
    "會員等級" character varying,
    "會員資格變更日" character varying,
    "會員資格到期日" character varying,
    "黑名單" character varying,
    "黑名單生效日" character varying,
    "赦免帳號" character varying,
    "接收電子報" character varying,
    "建立時間" character varying,
    "上次登入時間" character varying,
    "上次交易時間" character varying,
    "會員備註" character varying,
    year_old_range character varying,
    city character varying,
    item_id character varying,
    item_name character varying,
    order_id character varying,
    search_id character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.aroo_item_zh OWNER TO gpadmin;

--
-- Name: aroo_member_circumstance; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.aroo_member_circumstance (
    "帳號類型" character varying,
    "會員帳號" character varying,
    "姓名" character varying,
    "電話" character varying,
    "地址" character varying,
    "EMAIL" character varying,
    "驗證電話" character varying,
    "年齡" character varying,
    "生日" character varying,
    "購物金" character varying,
    "紅利點數" character varying,
    "交易總金額" character varying,
    "交易總次數" character varying,
    "交易金額-USHOP1號店" character varying,
    "交易次數-USHOP1號店" character varying,
    "交易金額-USHOP0號店" character varying,
    "交易次數-USHOP0號店" character varying,
    "會員等級" character varying,
    "會員資格變更日" character varying,
    "會員資格到期日" character varying,
    "黑名單" character varying,
    "黑名單生效日" character varying,
    "赦免帳號" character varying,
    "接收電子報" character varying,
    "建立時間" character varying,
    "上次登入時間" character varying,
    "上次交易時間" character varying,
    "會員備註" character varying,
    year_old_range character varying,
    city character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.aroo_member_circumstance OWNER TO gpadmin;

--
-- Name: aroo_report_location; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.aroo_report_location (
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    category6 character varying,
    reward numeric,
    created_time timestamp without time zone,
    updated_time timestamp without time zone,
    member_level character varying,
    store_address character varying,
    item_name character varying,
    address character varying,
    payment_status character varying,
    "Member Name" character varying,
    "Member Phone" character varying,
    "Member Email" character varying,
    "Account" character varying,
    "Remain Point" character varying,
    "Total Point" character varying,
    row_number bigint,
    order_delivery_date character varying,
    year bigint,
    city character varying,
    search_id character varying,
    size character varying,
    coupon_code character varying,
    year_old_range character varying,
    area character varying,
    district character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.aroo_report_location OWNER TO gpadmin;

--
-- Name: cn_hk_revenue; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.cn_hk_revenue (
    mabelle bigint,
    "join" bigint,
    yinjie bigint,
    other bigint,
    mabelle_revenue numeric,
    join_revenue numeric,
    yinjie_revenue numeric,
    other_revenue numeric,
    date date
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.cn_hk_revenue OWNER TO gpadmin;

--
-- Name: crm_tx_format; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.crm_tx_format (
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    city character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    category6 character varying,
    category7 character varying,
    category8 character varying,
    category9 character varying,
    category10 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone,
    siteid bigint
)
 DISTRIBUTED BY (tx_id);


ALTER TABLE report.crm_tx_format OWNER TO gpadmin;

--
-- Name: crm_tx_format_detail; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.crm_tx_format_detail (
    item_name character varying,
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    city character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    category6 character varying,
    category7 character varying,
    category8 character varying,
    category9 character varying,
    category10 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone,
    siteid bigint
)
 DISTRIBUTED BY (item_name);


ALTER TABLE report.crm_tx_format_detail OWNER TO gpadmin;

--
-- Name: ec_revenue_report; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.ec_revenue_report (
    siteid bigint,
    date date,
    site_name character varying,
    ec_profit_rate numeric,
    kol_profit_rate numeric,
    basic numeric,
    kol_source character varying,
    quantity integer,
    retchat_revenue numeric,
    kol_revenue numeric,
    itemcode character varying,
    price numeric,
    retchat_profit numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.ec_revenue_report OWNER TO gpadmin;

--
-- Name: edm_daily; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.edm_daily (
    id4 character varying,
    name character varying,
    ad character varying,
    groups character varying,
    campaign character varying,
    date date,
    click_sitemember bigint,
    open_sitemember bigint,
    total_click bigint,
    total_impression bigint,
    total_sitemember bigint,
    open_rate numeric,
    ctr numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.edm_daily OWNER TO gpadmin;

--
-- Name: edm_total; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.edm_total (
    id4 character varying,
    name character varying,
    ad character varying,
    groups character varying,
    campaign character varying,
    open_sitemember bigint,
    total_click bigint,
    total_impression bigint,
    total_sitemember bigint,
    open_rate numeric,
    ctr numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.edm_total OWNER TO gpadmin;

--
-- Name: eightmore_ta_tx_format; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.eightmore_ta_tx_format (
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    city character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    category6 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.eightmore_ta_tx_format OWNER TO gpadmin;

--
-- Name: eightmore_ta_tx_format_detail; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.eightmore_ta_tx_format_detail (
    txid character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    city character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    category6 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.eightmore_ta_tx_format_detail OWNER TO gpadmin;

--
-- Name: hair_ecommerce_member; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.hair_ecommerce_member (
    catatogy character varying,
    "ACCOUNT" character varying,
    segment character varying,
    "REMAIN_POINT" character varying,
    "TOTAL_POINT" character varying,
    income character varying,
    ismember bigint,
    phone character varying,
    address character varying,
    created_time date,
    "NAME" character varying,
    "EMAIL" character varying,
    gender character varying,
    member_level character varying,
    row_number bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.hair_ecommerce_member OWNER TO gpadmin;

--
-- Name: hair_report; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.hair_report (
    "日期" character varying,
    "訂單編號" character varying,
    "付款方式" character varying,
    "寄送方式" character varying,
    "E-MAIL" character varying,
    "帳號" character varying,
    "姓名" character varying,
    "電話" character varying,
    "地址" character varying,
    "明細" character varying,
    "金額驗算" character varying,
    "網站訂單編號" character varying,
    "發票金額" character varying,
    "單號" character varying,
    "發票抬頭" character varying,
    "統編" character varying,
    "信用卡後四碼" character varying,
    "備註" character varying,
    "來回件" character varying,
    "紅利電話" character varying,
    "配送結果" character varying,
    "發票號碼" character varying,
    "發票金額-發票實開金額" character varying,
    source character varying,
    revenue integer,
    is_ticket bigint,
    date date,
    three_catagory character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.hair_report OWNER TO gpadmin;

--
-- Name: hair_report_20230608_backup; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.hair_report_20230608_backup (
    "日期" character varying,
    "訂單編號" character varying,
    "付款方式" character varying,
    "寄送方式" character varying,
    "E-MAIL" character varying,
    "帳號" character varying,
    "姓名" character varying,
    "電話" character varying,
    "地址" character varying,
    "明細" character varying,
    "金額驗算" character varying,
    "網站訂單編號" character varying,
    "發票金額" character varying,
    "單號" character varying,
    "發票抬頭" character varying,
    "統編" character varying,
    "信用卡後四碼" character varying,
    "備註" character varying,
    "來回件" character varying,
    "紅利電話" character varying,
    "配送結果" character varying,
    "發票號碼" character varying,
    "發票金額-發票實開金額" character varying,
    source character varying,
    revenue integer,
    is_ticket bigint,
    date date,
    three_catagory character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.hair_report_20230608_backup OWNER TO gpadmin;

--
-- Name: hair_report_temp; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.hair_report_temp (
    "日期" character varying,
    "訂單編號" character varying,
    "付款方式" character varying,
    "寄送方式" character varying,
    "E-MAIL" character varying,
    "帳號" character varying,
    "姓名" character varying,
    "電話" character varying,
    "地址" character varying,
    "明細" character varying,
    "金額驗算" character varying,
    "網站訂單編號" character varying,
    "發票金額" character varying,
    "單號" character varying,
    "發票抬頭" character varying,
    "統編" character varying,
    "信用卡後四碼" character varying,
    "備註" character varying,
    "來回件" character varying,
    "紅利電話" character varying,
    "配送結果" character varying,
    "發票號碼" character varying,
    "發票金額-發票實開金額" character varying,
    source character varying,
    revenue integer,
    is_ticket bigint,
    date date,
    three_catagory character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.hair_report_temp OWNER TO gpadmin;

--
-- Name: kol_tracking_report; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.kol_tracking_report (
    tagkey text,
    month character varying,
    kol_source character varying,
    "MAU" bigint,
    "MPV" bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.kol_tracking_report OWNER TO gpadmin;

--
-- Name: pre_ec_revenue_report; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.pre_ec_revenue_report (
    siteid bigint,
    date date,
    site_name character varying,
    ec_profit_rate numeric,
    kol_profit_rate numeric,
    basic numeric,
    kol_source character varying,
    quantity integer,
    "hm.price" numeric,
    retchat_revenue numeric,
    kol_revenue numeric,
    itemcode character varying,
    price numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.pre_ec_revenue_report OWNER TO gpadmin;

--
-- Name: recommend_daily; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.recommend_daily (
    category character varying(255),
    "grouping" character varying(255),
    id4 character varying,
    date date,
    sum_impr_count bigint,
    sum_clk_count bigint,
    updated_time timestamp without time zone,
    recommend_first character varying,
    name_last character varying,
    vitemcode character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.recommend_daily OWNER TO gpadmin;

--
-- Name: smb_abandon_list; Type: TABLE; Schema: report; Owner: dac_dev; Tablespace: 
--

CREATE TABLE report.smb_abandon_list (
    retuid text,
    siteid bigint,
    sitemember text,
    itemcart text,
    date date,
    created_time timestamp without time zone,
    is_abandont bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_abandon_list OWNER TO dac_dev;

--
-- Name: smb_abandoned_list_traffic; Type: TABLE; Schema: report; Owner: dac_dev; Tablespace: 
--

CREATE TABLE report.smb_abandoned_list_traffic (
    is_abandont bigint,
    campaign text,
    retuid text,
    siteid bigint,
    sitemember text,
    itemorder text,
    itemcart text,
    stage character varying,
    date date,
    created_time timestamp without time zone,
    sync character varying,
    source character varying,
    segment character varying,
    city character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_abandoned_list_traffic OWNER TO dac_dev;

--
-- Name: smb_catgory_analysis; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_catgory_analysis (
    siteid bigint,
    segment character varying,
    date date,
    year character varying,
    category6 character varying,
    category_tx integer,
    category_amount numeric,
    category_num integer,
    total_tx bigint,
    total_amount numeric,
    total_num bigint,
    "Segment" character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_catgory_analysis OWNER TO gpadmin;

--
-- Name: smb_email_analysis; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_email_analysis (
    name character varying,
    campaign character varying,
    edm_total_msg numeric,
    edm_open_msg numeric,
    edm_click_msg numeric,
    edm_success_msg numeric,
    edm_success_rate numeric,
    edm_conversion numeric,
    unsubscribe_rate numeric,
    click_rate numeric,
    open_rate numeric,
    open_click_rate numeric,
    siteid bigint,
    date date
)
WITH (appendonly='true', orientation='row', compresstype=zlib, compresslevel='9')
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_email_analysis OWNER TO gpadmin;

--
-- Name: smb_email_analysis_daily; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_email_analysis_daily (
    date date,
    name character varying,
    siteid bigint,
    edm_open_rate numeric,
    edm_click_rate numeric,
    edm_cto_rate numeric,
    edm_unsubscribe_rate numeric,
    edm_convert_rate numeric,
    edm_total_msg bigint,
    edm_open_msg bigint,
    edm_click_msg bigint,
    edm_unsubscribe_msg bigint,
    edm_convert_msg bigint,
    campaign character varying,
    bought_tx_num bigint,
    bought_amount bigint,
    bought_member_count bigint,
    short_term_bought_tx_num bigint,
    short_term_bought_amount bigint,
    short_term_bought_member_count bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_email_analysis_daily OWNER TO gpadmin;

--
-- Name: smb_email_analysis_script; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_email_analysis_script (
    name character varying,
    campaign text,
    siteid bigint,
    sum_short_term_bought_member_count bigint,
    sum_short_term_bought_amount bigint,
    sum_short_term_bought_tx_num bigint,
    sum_bought_member_count bigint,
    sum_bought_amount bigint,
    sum_bought_tx_num bigint,
    first_date date,
    latest_date date,
    edm_total_msg bigint,
    edm_open_msg bigint,
    edm_click_msg bigint,
    edm_unsubscribe_msg bigint,
    edm_convert_msg bigint,
    edm_open_rate numeric,
    edm_click_rate numeric,
    edm_cto_rate numeric,
    edm_unsubscribe_rate numeric,
    edm_convert_rate numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_email_analysis_script OWNER TO gpadmin;

--
-- Name: smb_email_effective_daily; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_email_effective_daily (
    created_date date,
    siteid bigint,
    count_distinct_tx_id bigint,
    sum_amount numeric,
    short_tx bigint,
    short_amount numeric,
    long_tx bigint,
    long_amount numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_email_effective_daily OWNER TO gpadmin;

--
-- Name: smb_flow_tx_format; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_flow_tx_format (
    category10 character varying,
    category9 character varying,
    category8 character varying,
    category7 character varying,
    "Account" character varying,
    updated_time timestamp without time zone,
    created_time timestamp without time zone,
    category6 character varying,
    category5 character varying,
    category4 character varying,
    category3 character varying,
    category2 character varying,
    category1 character varying,
    city character varying,
    store_id character varying,
    item_id character varying,
    num integer,
    amount numeric,
    uid character varying,
    siteid bigint,
    tx_id character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_flow_tx_format OWNER TO gpadmin;

--
-- Name: smb_item_analysis; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_item_analysis (
    siteid bigint,
    date date,
    item_id character varying,
    segment character varying,
    year character varying,
    category6 character varying,
    category_tx numeric,
    category_amount numeric,
    category_num numeric,
    total_tx bigint,
    total_amount bigint,
    total_num bigint,
    "Segment" character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_item_analysis OWNER TO gpadmin;

--
-- Name: smb_line_member; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_line_member (
    siteid bigint,
    sitemember text,
    max_date date,
    min_date date,
    count_retuid bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_line_member OWNER TO gpadmin;

--
-- Name: smb_line_member_count; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_line_member_count (
    siteid bigint,
    date date,
    member_count bigint
)
 DISTRIBUTED BY (siteid, date);


ALTER TABLE report.smb_line_member_count OWNER TO gpadmin;

--
-- Name: smb_marketing_overview; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_marketing_overview (
    siteid bigint,
    phone_count bigint,
    email_count bigint,
    sms_total_msg bigint,
    sms_conversion numeric,
    line_total_msg bigint,
    line_conversion numeric,
    total_register_num bigint,
    line_count bigint,
    edm_total_msg bigint,
    email_conversion numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_marketing_overview OWNER TO gpadmin;

--
-- Name: smb_member_info; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_member_info (
    category10 character varying,
    category9 character varying,
    category8 character varying,
    category7 character varying,
    item_name character varying,
    store_address character varying,
    address character varying,
    payment_status text,
    row_number bigint,
    "Total_Point" character varying,
    "Remain_Point" character varying,
    "Account" character varying,
    "Member_Email" character varying,
    "Member_Phone" character varying,
    "Member_Name" character varying,
    member_level character varying,
    year bigint,
    updated_time timestamp without time zone,
    created_time timestamp without time zone,
    category6 character varying,
    category5 character varying,
    category4 character varying,
    category3 character varying,
    category2 character varying,
    category1 character varying,
    city character varying,
    store_id character varying,
    item_id character varying,
    num integer,
    amount numeric,
    uid character varying,
    siteid bigint,
    tx_id character varying,
    member_row_number bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_member_info OWNER TO gpadmin;

--
-- Name: smb_member_upload; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_member_upload (
    "Member_Phone" character varying,
    "Member_Email" character varying,
    "Account" character varying,
    register_time date,
    siteid bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_member_upload OWNER TO gpadmin;

--
-- Name: smb_new_old_customer; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_new_old_customer (
    tx_id character varying,
    uid character varying,
    amount numeric,
    item_id character varying,
    siteid bigint,
    avg_repurchased_days bigint,
    date date,
    new_customer_tag character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_new_old_customer OWNER TO gpadmin;

--
-- Name: smb_performance; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_performance (
    siteid bigint,
    date date,
    avg_order_value numeric,
    total_pageview bigint,
    order_conversion numeric,
    order_quantity bigint,
    revenue numeric,
    order_quantity_website numeric,
    created_date date,
    email_count bigint,
    phone_count bigint,
    account_count bigint,
    line_count bigint,
    new_register_num bigint,
    new_line_sync_count bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_performance OWNER TO gpadmin;

--
-- Name: smb_performance_tmp; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_performance_tmp (
    siteid bigint,
    date date,
    avg_order_value numeric,
    total_pageview bigint,
    order_conversion numeric,
    order_quantity bigint,
    revenue numeric,
    new_register_num bigint,
    email_count bigint,
    phone_count bigint,
    sms_msg_count bigint,
    line_msg_count bigint,
    email_conversion bigint,
    sms_conversion bigint,
    line_conversion bigint,
    line_count bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_performance_tmp OWNER TO gpadmin;

--
-- Name: smb_preference_result; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_preference_result (
    siteid bigint,
    vipcode character varying,
    productcode character varying,
    count_productcode bigint,
    sum_skunetprice numeric,
    avg_skunetprice numeric,
    stddev_skunetprice numeric,
    "product.avg_skunetprice" numeric,
    max_avg_skunetprice numeric,
    "QFLAG" integer,
    "SFLAG" integer,
    preference bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_preference_result OWNER TO gpadmin;

--
-- Name: smb_preference_result_test; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_preference_result_test (
    siteid bigint,
    vipcode character varying,
    productcode character varying,
    count_productcode bigint,
    sum_skunetprice numeric,
    avg_skunetprice numeric,
    stddev_skunetprice numeric,
    "product.avg_skunetprice" numeric,
    max_avg_skunetprice numeric,
    "QFLAG" integer,
    "SFLAG" integer,
    preference bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_preference_result_test OWNER TO gpadmin;

--
-- Name: smb_rec_effective_daily; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_rec_effective_daily (
    created_date date,
    siteid bigint,
    count_distinct_tx_id bigint,
    sum_amount numeric,
    short_tx bigint,
    short_amount numeric,
    long_tx bigint,
    long_amount numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_rec_effective_daily OWNER TO gpadmin;

--
-- Name: smb_recommend; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_recommend (
    category character varying(255),
    "grouping" character varying(255),
    date date,
    sum_impr_count bigint,
    sum_clk_count bigint,
    updated_time timestamp without time zone,
    recommend_first character varying,
    name_last character varying,
    vitemcode character varying,
    siteid character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_recommend OWNER TO gpadmin;

--
-- Name: smb_recommend_daily; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_recommend_daily (
    category character varying(255),
    "grouping" character varying(255),
    date date,
    sum_impr_count bigint,
    sum_clk_count bigint,
    updated_time timestamp without time zone,
    recommend_first character varying,
    name_last character varying,
    vitemcode character varying,
    siteid character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_recommend_daily OWNER TO gpadmin;

--
-- Name: smb_recommend_result; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_recommend_result (
    category character varying(255),
    "grouping" character varying(255),
    date date,
    sum_impr_count bigint,
    sum_clk_count bigint,
    updated_time timestamp without time zone,
    recommend_first character varying,
    name_last character varying,
    vitemcode character varying,
    siteid character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_recommend_result OWNER TO gpadmin;

--
-- Name: smb_repurchaed_analysis_days; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_repurchaed_analysis_days (
    repurchased_weeks bigint,
    count_customers bigint,
    siteid bigint,
    date date
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_repurchaed_analysis_days OWNER TO gpadmin;

--
-- Name: smb_repurchaed_analysis_number; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_repurchaed_analysis_number (
    onetime_customers bigint,
    total_customers bigint,
    date date,
    siteid bigint,
    avg_repurchased_days bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_repurchaed_analysis_number OWNER TO gpadmin;

--
-- Name: smb_repurchased_analysis_days; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_repurchased_analysis_days (
    siteid bigint,
    repurchased_weeks bigint,
    count_customers bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_repurchased_analysis_days OWNER TO gpadmin;

--
-- Name: smb_repurchased_analysis_number; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_repurchased_analysis_number (
    avg_repurchased_days bigint,
    siteid bigint,
    total_customers bigint,
    onetime_customers bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_repurchased_analysis_number OWNER TO gpadmin;

--
-- Name: smb_rfm_analysis; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_rfm_analysis (
    lifetime_value double precision,
    uid character varying,
    siteid bigint,
    statistics_date date,
    "R" bigint,
    "F" bigint,
    "M" bigint,
    segment character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_rfm_analysis OWNER TO gpadmin;

--
-- Name: smb_rfm_result; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_rfm_result (
    avg_amount numeric,
    most_freq_hour bigint,
    most_freq_dow bigint,
    most_freq_date bigint,
    num_city bigint,
    num_store bigint,
    lifetime_visit bigint,
    lifetime_value double precision,
    last_price bigint,
    last_store character varying,
    last_city character varying,
    last_time timestamp without time zone,
    last_dow bigint,
    last_date bigint,
    duration_day integer,
    duration_year integer,
    last_year_visit bigint,
    last_year_total_amout numeric,
    last_year_avg_amount numeric,
    frequency numeric,
    recency bigint,
    "R" character varying,
    "F" character varying,
    "M" character varying,
    duration_day_bin bigint,
    avg_amount_bin bigint,
    frequency_bin bigint,
    recency_bin bigint,
    siteid bigint,
    uid character varying,
    segment integer,
    first_visit_time timestamp without time zone
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_rfm_result OWNER TO gpadmin;

--
-- Name: smb_rfm_result_acc_weekly; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_rfm_result_acc_weekly (
    uid character varying,
    segment integer,
    first_visit_time timestamp without time zone,
    siteid bigint,
    time_slot date
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_rfm_result_acc_weekly OWNER TO gpadmin;

--
-- Name: smb_sms_analysis_daily; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_sms_analysis_daily (
    date date,
    name character varying,
    siteid bigint,
    sms_open_rate numeric,
    sms_click_rate numeric,
    sms_cto_rate numeric,
    sms_unsubscribe_rate numeric,
    sms_convert_rate numeric,
    sms_total_msg bigint,
    sms_open_msg bigint,
    sms_click_msg bigint,
    sms_unsubscribe_msg bigint,
    sms_convert_msg bigint,
    campaign character varying,
    bought_tx_num bigint,
    bought_amount bigint,
    bought_member_count bigint,
    short_term_bought_tx_num bigint,
    short_term_bought_amount bigint,
    short_term_bought_member_count bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_sms_analysis_daily OWNER TO gpadmin;

--
-- Name: smb_sms_analysis_script; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_sms_analysis_script (
    name character varying,
    campaign text,
    siteid bigint,
    sum_short_term_bought_member_count bigint,
    sum_short_term_bought_amount bigint,
    sum_short_term_bought_tx_num bigint,
    sum_bought_member_count bigint,
    sum_bought_amount bigint,
    sum_bought_tx_num bigint,
    first_date date,
    latest_date date,
    sms_total_msg bigint,
    sms_open_msg bigint,
    sms_click_msg bigint,
    sms_unsubscribe_msg bigint,
    sms_convert_msg bigint,
    sms_open_rate numeric,
    sms_click_rate numeric,
    sms_cto_rate numeric,
    sms_unsubscribe_rate numeric,
    sms_convert_rate numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_sms_analysis_script OWNER TO gpadmin;

--
-- Name: smb_sms_effective_daily; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_sms_effective_daily (
    created_date date,
    siteid bigint,
    count_distinct_tx_id bigint,
    sum_amount numeric,
    short_tx bigint,
    short_amount numeric,
    long_tx bigint,
    long_amount numeric
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_sms_effective_daily OWNER TO gpadmin;

--
-- Name: smb_sms_total_statistics; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_sms_total_statistics (
    date_that_counts date,
    tagkey character varying,
    sum_sum_click_count bigint,
    sum_sum_impression_count bigint,
    pixelid character varying(255),
    type character varying,
    id4 character varying,
    date date,
    name character varying,
    remark text,
    content text,
    term text,
    campaign text,
    groups text,
    ad text,
    start_send_time timestamp without time zone,
    total_count bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_sms_total_statistics OWNER TO gpadmin;

--
-- Name: smb_total_statistics; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_total_statistics (
    tagkey character varying,
    name character varying,
    campaign character varying,
    groups character varying,
    ad character varying,
    date date,
    id4 character varying,
    last_time timestamp without time zone,
    sum_click_count bigint,
    sum_impression_count bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_total_statistics OWNER TO gpadmin;

--
-- Name: smb_traffic; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_traffic (
    campaign text,
    retuid text,
    siteid bigint,
    sitemember text,
    itemorder text,
    itemcart text,
    stage character varying,
    date date,
    created_time timestamp without time zone,
    sync character varying,
    source character varying,
    segment character varying,
    city character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_traffic OWNER TO gpadmin;

--
-- Name: smb_traffic_summary; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_traffic_summary (
    siteid bigint,
    view_uu numeric,
    discover_uu numeric,
    consider_uu numeric,
    desire_uu numeric,
    checkout_uu numeric,
    purchased_uu numeric,
    date date
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_traffic_summary OWNER TO gpadmin;

--
-- Name: smb_traffic_summary_old; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_traffic_summary_old (
    siteid bigint,
    view_uu numeric,
    discover_uu numeric,
    consider_uu numeric,
    desire_uu numeric,
    checkout_uu numeric,
    purchased_uu numeric,
    discover_conversion numeric,
    consider_conversion numeric,
    desire_conversion numeric,
    checkout_conversion numeric,
    purchased_conversion numeric,
    date date
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_traffic_summary_old OWNER TO gpadmin;

--
-- Name: smb_tx_edm; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_tx_edm (
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    city character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone,
    category6 character varying,
    siteid bigint,
    created_date date,
    short_first_time timestamp without time zone,
    short_has_mail bigint,
    long_first_time timestamp without time zone,
    long_has_mail bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_tx_edm OWNER TO gpadmin;

--
-- Name: smb_tx_format; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_tx_format (
    order_source character varying,
    category10 character varying,
    category9 character varying,
    category8 character varying,
    category7 character varying,
    "Account" character varying,
    updated_time timestamp without time zone,
    created_time timestamp without time zone,
    category6 character varying,
    category5 character varying,
    category4 character varying,
    category3 character varying,
    category2 character varying,
    category1 character varying,
    city character varying,
    store_id character varying,
    item_id character varying,
    num integer,
    amount numeric,
    uid character varying,
    siteid bigint,
    tx_id character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_tx_format OWNER TO gpadmin;

--
-- Name: smb_tx_format_detail; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_tx_format_detail (
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    city character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    category6 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone,
    item_name character varying,
    siteid bigint,
    category7 character varying,
    category8 character varying,
    category9 character varying,
    category10 character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_tx_format_detail OWNER TO gpadmin;

--
-- Name: smb_tx_format_detail_test; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_tx_format_detail_test (
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    city character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    category6 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone,
    item_name character varying,
    siteid bigint,
    category7 character varying,
    category8 character varying,
    category9 character varying,
    category10 character varying
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_tx_format_detail_test OWNER TO gpadmin;

--
-- Name: smb_tx_rec; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_tx_rec (
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone,
    category6 character varying,
    siteid bigint,
    created_date date,
    short_last_time timestamp without time zone,
    short_has_rec bigint,
    long_last_time timestamp without time zone,
    long_has_rec bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_tx_rec OWNER TO gpadmin;

--
-- Name: smb_tx_sms; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.smb_tx_sms (
    tx_id character varying,
    uid character varying,
    amount numeric,
    num integer,
    item_id character varying,
    store_id character varying,
    city character varying,
    category1 character varying,
    category2 character varying,
    category3 character varying,
    category4 character varying,
    category5 character varying,
    created_time timestamp without time zone,
    updated_time timestamp without time zone,
    category6 character varying,
    siteid bigint,
    created_date date,
    short_first_time timestamp without time zone,
    short_has_sms bigint,
    long_first_time timestamp without time zone,
    long_has_sms bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.smb_tx_sms OWNER TO gpadmin;

--
-- Name: stage_traffic_analysis; Type: TABLE; Schema: report; Owner: gpadmin; Tablespace: 
--

CREATE TABLE report.stage_traffic_analysis (
    priority integer,
    page_intent text,
    page_type text,
    semantic_tags text[],
    campaign text,
    name character varying,
    retuid text,
    url text,
    siteid bigint,
    sitemember text,
    itemorder text,
    itemcart text,
    tagkey text,
    stage character varying,
    date date,
    created_time timestamp without time zone,
    url_trim character varying,
    url_norm character varying,
    path character varying,
    query character varying,
    product_id bigint,
    stage_norm character varying,
    event_id character varying,
    row_number bigint
)
 DISTRIBUTED RANDOMLY;


ALTER TABLE report.stage_traffic_analysis OWNER TO gpadmin;

