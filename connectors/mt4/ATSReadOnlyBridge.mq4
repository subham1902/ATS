#property strict
// Attach to the configured broker gold chart. AutoTrading may stay disabled.
// This EA only reads quotes/metadata and writes an atomic file in Common/Files.
input string BrokerSymbol = "XAUUSD";
input string SnapshotFile = "ats-xauusd-mt4.json";

string Number(double value) { return DoubleToString(value, 12); }

int OnInit() {
   if(Symbol() != BrokerSymbol) return INIT_PARAMETERS_INCORRECT;
   return INIT_SUCCEEDED;
}

void OnTick() {
   double bid = MarketInfo(BrokerSymbol, MODE_BID);
   double ask = MarketInfo(BrokerSymbol, MODE_ASK);
   if(bid <= 0 || ask < bid) return;
   double point = MarketInfo(BrokerSymbol, MODE_POINT);
   double tickSize = MarketInfo(BrokerSymbol, MODE_TICKSIZE) * point;
   if(point <= 0 || tickSize <= 0) return;
   string document = "{\"schema_version\":\"ats-mt4-readonly-v1\",\"metadata\":{";
   document += "\"name\":\"" + BrokerSymbol + "\",\"digits\":" + IntegerToString((int)MarketInfo(BrokerSymbol,MODE_DIGITS));
   document += ",\"point\":"+Number(point)+",\"trade_tick_size\":"+Number(tickSize);
   document += ",\"trade_contract_size\":"+Number(MarketInfo(BrokerSymbol,MODE_LOTSIZE));
   document += ",\"volume_min\":"+Number(MarketInfo(BrokerSymbol,MODE_MINLOT));
   document += ",\"volume_max\":"+Number(MarketInfo(BrokerSymbol,MODE_MAXLOT));
   document += ",\"volume_step\":"+Number(MarketInfo(BrokerSymbol,MODE_LOTSTEP));
   document += ",\"trade_mode\":"+(MarketInfo(BrokerSymbol,MODE_TRADEALLOWED)>0 ? "4" : "0");
   document += "},\"tick\":{\"symbol\":\""+BrokerSymbol+"\",\"time\":"+IntegerToString((int)TimeGMT());
   document += ",\"timestamp_provenance\":\"TERMINAL_RECEIVE_UTC\",\"bid\":"+Number(bid)+",\"ask\":"+Number(ask)+"}}";
   string temporary = SnapshotFile + ".tmp";
   int handle = FileOpen(temporary, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle == INVALID_HANDLE) return;
   FileWriteString(handle, document);
   FileFlush(handle);
   FileClose(handle);
   FileMove(temporary, FILE_COMMON, SnapshotFile, FILE_COMMON|FILE_REWRITE);
}
