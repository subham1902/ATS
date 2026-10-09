#property strict
#property version "1.000"
#property description "ATS XAUUSD small-account observation bridge. No execution authority."

// This EA never imports Trade.mqh, submits orders, or changes terminal permissions.
// The approved ATS external adapter remains the only future execution route.
input string ATSAccountId="";
input string BrokerSymbol="XAUUSD";
input string ResearchPresetHash="UNVALIDATED";
input string Strategy1Id="XAU-018";
input string Strategy2Id="XAU-019";
input string Strategy3Id="XAU-020";
input int StrategyVersion=1;
input bool RequireDemoAccount=true;
input int PublishSeconds=2;
input double ResearchRiskFraction=0.005;
input double RequestedDailyLossFraction=0.03;
input double RequestedMonthlyLossFraction=0.08;
input string ClockProfileCsv="";
input string ClockProfileHash="";
input int HistoryWarmupDays=120;
input int TacticalSeconds=60;
input int TacticalLookback=1;
input int EnabledStrategyMask=7;
input double TargetR=2.0;
input bool EnableProfitProtection=true;
input int MaximumHoldMinutes=120;
input double EstimatedRoundTripCostPerLot=44.0;
input int MinimumEntryHourUTC=6;
input int MaximumEntryHourUTC=20;
input int AllowedWeekdayMask=127;
input int AllowedDirectionMask=3;

string state_file="",journal_file="";
long last_tick_msc=-1;
long expected_login=0;
string expected_server="";
bool busy=false;

string Esc(string value) {
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r","\\r");
   StringReplace(value,"\n","\\n");
   StringReplace(value,"\t","\\t");
   return value;
}
string Quote(string value) { return "\""+Esc(value)+"\""; }
string Truth(bool value) { return value?"true":"false"; }
string Number(double value,int digits=8) {
   return MathIsValidNumber(value)?DoubleToString(value,digits):"null";
}
string OptionalPositive(double value,int digits=8) {
   return value>0?Number(value,digits):"null";
}
string AccountMode() {
   long mode=AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(mode==ACCOUNT_TRADE_MODE_DEMO)return "DEMO";
   if(mode==ACCOUNT_TRADE_MODE_REAL)return "LIVE";
   return "UNKNOWN";
}
bool Identity() {
   return AccountInfoInteger(ACCOUNT_LOGIN)==expected_login &&
          AccountInfoString(ACCOUNT_SERVER)==expected_server;
}
bool Store(string filename,string payload,bool append=false) {
   string target=append?filename:filename+".tmp";
   int flags=FILE_TXT|FILE_ANSI|FILE_WRITE;
   if(append)flags|=FILE_READ|FILE_SHARE_READ;
   int handle=FileOpen(target,flags,0,CP_UTF8);
   if(handle==INVALID_HANDLE)return false;
   if(append)FileSeek(handle,0,SEEK_END);
   bool ok=FileWriteString(handle,payload+"\n")>0;
   FileFlush(handle);FileClose(handle);
   if(!ok)return false;
   if(!append)return FileMove(target,0,filename,FILE_REWRITE);
   return true;
}
string Positions() {
   string out="[";int observed=0;
   for(int i=0;i<PositionsTotal();i++) {
      ulong ticket=PositionGetTicket(i);
      if(ticket==0)continue;
      if(PositionGetString(POSITION_SYMBOL)!=BrokerSymbol)continue;
      if(observed++>0)out+=",";
      out+="{\"broker_position_id\":"+Quote(IntegerToString((long)ticket))+
         ",\"canonical_symbol\":\"XAUUSD\",\"source_symbol\":"+Quote(BrokerSymbol)+
         ",\"side\":"+Quote(PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY?"BUY":"SELL")+
         ",\"volume\":"+Number(PositionGetDouble(POSITION_VOLUME))+
         ",\"entry\":"+Number(PositionGetDouble(POSITION_PRICE_OPEN))+
         ",\"sl\":"+OptionalPositive(PositionGetDouble(POSITION_SL))+
         ",\"tp\":"+OptionalPositive(PositionGetDouble(POSITION_TP))+
         ",\"floating_profit\":"+Number(PositionGetDouble(POSITION_PROFIT))+
         ",\"swap\":"+Number(PositionGetDouble(POSITION_SWAP))+
         ",\"magic\":"+Quote(IntegerToString(PositionGetInteger(POSITION_MAGIC)))+"}";
   }
   return out+"]";
}
string Metadata() {
   return "{\"digits\":"+IntegerToString(SymbolInfoInteger(BrokerSymbol,SYMBOL_DIGITS))+
      ",\"point\":"+OptionalPositive(SymbolInfoDouble(BrokerSymbol,SYMBOL_POINT))+
      ",\"tick_size\":"+OptionalPositive(SymbolInfoDouble(BrokerSymbol,SYMBOL_TRADE_TICK_SIZE))+
      ",\"contract_size\":"+OptionalPositive(SymbolInfoDouble(BrokerSymbol,SYMBOL_TRADE_CONTRACT_SIZE))+
      ",\"volume_min\":"+OptionalPositive(SymbolInfoDouble(BrokerSymbol,SYMBOL_VOLUME_MIN))+
      ",\"volume_max\":"+OptionalPositive(SymbolInfoDouble(BrokerSymbol,SYMBOL_VOLUME_MAX))+
      ",\"volume_step\":"+OptionalPositive(SymbolInfoDouble(BrokerSymbol,SYMBOL_VOLUME_STEP))+
      ",\"trade_mode\":"+IntegerToString(SymbolInfoInteger(BrokerSymbol,SYMBOL_TRADE_MODE))+
      ",\"base_currency\":"+Quote(SymbolInfoString(BrokerSymbol,SYMBOL_CURRENCY_BASE))+
      ",\"quote_currency\":"+Quote(SymbolInfoString(BrokerSymbol,SYMBOL_CURRENCY_PROFIT))+"}";
}
#include "SmallAccountSignals.mqh"
void Publish() {
   bool connected=(bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   bool identity=Identity();
   string mode=AccountMode();
   string status=!identity?"ACCOUNT_CHANGED":(!connected?"DISCONNECTED":"OBSERVING");
   if(RequireDemoAccount && mode!="DEMO")status="EXPECTED_DEMO_ACCOUNT";
   MqlTick tick;ZeroMemory(tick);
   bool has_tick=identity && connected && SymbolInfoTick(BrokerSymbol,tick);
   bool valid=has_tick && tick.bid>0 && tick.ask>=tick.bid;
   // Broker timestamps are preserved raw. This observer cannot authorize a UTC
   // conversion for historical bars or silently assume a server offset/DST rule.
   string quote="null";
   if(valid) {
      quote="{\"raw_source_epoch_ms\":"+IntegerToString(tick.time_msc)+
         ",\"bid\":"+Number(tick.bid)+",\"ask\":"+Number(tick.ask)+
         ",\"spread\":"+Number(tick.ask-tick.bid)+
         ",\"last\":"+OptionalPositive(tick.last)+
         ",\"real_volume\":"+((tick.flags&TICK_FLAG_VOLUME)!=0?Number(tick.volume_real):"null")+
         ",\"broker_volume\":"+((tick.flags&TICK_FLAG_VOLUME)!=0?IntegerToString((long)tick.volume):"null")+
         ",\"flags\":"+IntegerToString(tick.flags)+
         ",\"provenance\":\"BROKER_TICK_PROXY\",\"clock_policy\":\"RAW_BROKER_TIME\"}";
   }
   datetime utc=TimeGMT();
   // Raw simultaneous anchors; an independent UTC observer must attest these.
   // They never establish a historical broker timezone/DST rule themselves.
   string clock_probe="{\"gmt\":"+IntegerToString((long)utc)+
      ",\"server_time\":"+IntegerToString((long)TimeTradeServer())+
      ",\"local\":"+IntegerToString((long)TimeLocal())+
      ",\"tick_msc\":"+IntegerToString(valid?tick.time_msc:0)+
      ",\"connected\":"+Truth(connected)+",\"algo_allowed\":"+
      Truth((bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))+
      ",\"server\":"+Quote(AccountInfoString(ACCOUNT_SERVER))+"}";
   if(identity && connected && valid)
      Store("ATS\\SmallAccount\\"+ATSAccountId+"\\clock-probe.json",clock_probe);
   string payload="{\"version\":\"ATS-MT5-OBSERVER-V1\",\"account_id\":"+Quote(ATSAccountId)+
      ",\"canonical_symbol\":\"XAUUSD\",\"broker_symbol\":"+Quote(BrokerSymbol)+
      ",\"platform\":\"MT5\",\"observed_at_utc\":"+IntegerToString((long)utc)+
      ",\"utc_source\":\"TERMINAL_TIMEGMT_REQUIRES_INDEPENDENT_VALIDATION\""+
      ",\"source_server\":"+Quote(AccountInfoString(ACCOUNT_SERVER))+
      ",\"account_mode\":"+Quote(mode)+",\"connection_state\":"+Quote(status)+
      ",\"identity_matches\":"+Truth(identity)+
      ",\"terminal_algo_allowed\":"+Truth((bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))+
      ",\"ea_trade_allowed\":"+Truth((bool)MQLInfoInteger(MQL_TRADE_ALLOWED))+
      ",\"account_trade_allowed\":"+Truth((bool)AccountInfoInteger(ACCOUNT_TRADE_ALLOWED))+
      ",\"account_expert_allowed\":"+Truth((bool)AccountInfoInteger(ACCOUNT_TRADE_EXPERT))+
      ",\"execution_authority\":\"NONE\",\"commands_supported\":false"+
      ",\"balance\":"+(identity?Number(AccountInfoDouble(ACCOUNT_BALANCE)):"null")+
      ",\"equity\":"+(identity?Number(AccountInfoDouble(ACCOUNT_EQUITY)):"null")+
      ",\"free_margin\":"+(identity?Number(AccountInfoDouble(ACCOUNT_MARGIN_FREE)):"null")+
      ",\"currency\":"+Quote(AccountInfoString(ACCOUNT_CURRENCY))+
      ",\"research_preset_hash\":"+Quote(ResearchPresetHash)+
      ",\"strategy_version\":"+IntegerToString(StrategyVersion)+
      ",\"planned_risk_fraction\":"+Number(ResearchRiskFraction)+
      ",\"requested_daily_booked_loss_fraction\":"+Number(RequestedDailyLossFraction)+
      ",\"requested_monthly_booked_loss_fraction\":"+Number(RequestedMonthlyLossFraction)+
      ",\"daily_net_realized\":null,\"month_net_realized\":null"+
      ",\"loss_baseline_status\":\"ATS_PERIOD_EQUITY_LEDGER_REQUIRED\""+
      ",\"quote\":"+quote+",\"symbol_metadata\":"+Metadata()+
      ",\"signal_status\":"+Quote(signal_status)+",\"latest_proposal\":"+latest_proposal+
      ",\"positions\":"+(identity?Positions():"[]")+"}";
   if(!Store(state_file,payload))status="PERSISTENCE_ERROR";
   if(valid && tick.time_msc!=last_tick_msc) {
      if(Store(journal_file,payload,true))last_tick_msc=tick.time_msc;
      else status="JOURNAL_ERROR";
   }
   Comment("ATS SMALL ACCOUNT OBSERVER | ",status,
      "\nCanonical XAUUSD | Broker ",BrokerSymbol," | ",mode,
      "\nExecution authority: NONE | ATS adapter authorization required",
      "\nSignal: ",signal_status," | Preset ",StringSubstr(ResearchPresetHash,0,12),
      "\nResearch caps: daily ",DoubleToString(100*RequestedDailyLossFraction,2),
      "% / month ",DoubleToString(100*RequestedMonthlyLossFraction,2),"%",
      "\nSource clock preserved raw; UTC period loss ledger is not connected.");
}
int OnInit() {
   if(ATSAccountId=="" || StringFind(ATSAccountId,"/")>=0 || StringFind(ATSAccountId,"\\")>=0 ||
      StringFind(ATSAccountId,"..")>=0 || PublishSeconds<1 || PublishSeconds>60 ||
      ResearchRiskFraction<=0 || ResearchRiskFraction>0.02 ||
      RequestedDailyLossFraction<=0 || RequestedDailyLossFraction>0.03 ||
      RequestedMonthlyLossFraction<=0 || RequestedMonthlyLossFraction>0.08 ||
      (TacticalSeconds!=60 && TacticalSeconds!=300) || (TacticalLookback!=1 && TacticalLookback!=3) ||
      EnabledStrategyMask<1 || EnabledStrategyMask>7 || TargetR<1 || TargetR>5 ||
      HistoryWarmupDays<75 || HistoryWarmupDays>730 || MaximumHoldMinutes<1 ||
      EstimatedRoundTripCostPerLot<0 || MinimumEntryHourUTC<0 || MaximumEntryHourUTC>24 ||
      MinimumEntryHourUTC>=MaximumEntryHourUTC || AllowedWeekdayMask<1 || AllowedWeekdayMask>127 ||
      AllowedDirectionMask<1 || AllowedDirectionMask>3 || StrategyVersion<1 ||
      Strategy1Id!="XAU-018" || Strategy2Id!="XAU-019" || Strategy3Id!="XAU-020")
      return INIT_PARAMETERS_INCORRECT;
   if(!SymbolSelect(BrokerSymbol,true))return INIT_FAILED;
   string base=SymbolInfoString(BrokerSymbol,SYMBOL_CURRENCY_BASE);
   string quote=SymbolInfoString(BrokerSymbol,SYMBOL_CURRENCY_PROFIT);
   if((base!="" && base!="XAU") || (quote!="" && quote!="USD"))return INIT_PARAMETERS_INCORRECT;
   if(RequireDemoAccount && AccountMode()!="DEMO")return INIT_FAILED;
   expected_login=AccountInfoInteger(ACCOUNT_LOGIN);
   expected_server=AccountInfoString(ACCOUNT_SERVER);
   FolderCreate("ATS");FolderCreate("ATS\\SmallAccount");
   string folder="ATS\\SmallAccount\\"+ATSAccountId;
   FolderCreate(folder);
   state_file=folder+"\\account-state.json";
   journal_file=folder+"\\observations.jsonl";
   if(ClockProfileCsv!="" && !LoadClockProfile())return INIT_PARAMETERS_INCORRECT;
   if(!EventSetTimer(PublishSeconds))return INIT_FAILED;
   Publish();return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { EventKillTimer();Comment(""); }
void OnTimer() { if(busy)return;busy=true;EvaluateSignals();Publish();busy=false; }
