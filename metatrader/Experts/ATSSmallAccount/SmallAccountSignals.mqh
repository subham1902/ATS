#ifndef ATS_SMALL_ACCOUNT_SIGNALS_MQH
#define ATS_SMALL_ACCOUNT_SIGNALS_MQH
#include "SmallAccountRules.mqh"

struct ATSClockSegment {long begin,end,offset;};
struct ATSParent {int side;long decision,expires;double level;};
ATSClockSegment clock_segments[];
ATSParent parents[3];
S1Bar source_h1[],source_h4[],source_h4_full[],tactical_bars[];
S2Bar source_h1_full[],source_m15[];
long last_signal_cycle=0;
string signal_status="CLOCK_PROFILE_REQUIRED",latest_proposal="null";

bool NumericInteger(string value) {
   if(value=="" || value=="-")return false;
   for(int i=0;i<StringLen(value);i++) {
      ushort code=StringGetCharacter(value,i);
      if(i==0 && code==45)continue;
      if(code<48 || code>57)return false;
   }
   return true;
}
string FileSha256(string file) {
   int h=FileOpen(file,FILE_READ|FILE_BIN);
   if(h==INVALID_HANDLE)return "";
   ulong size=FileSize(h);
   if(size==0 || size>1024*1024) {FileClose(h);return "";}
   uchar bytes[],key[],hash[];ArrayResize(bytes,(int)size);
   uint read=FileReadArray(h,bytes,0,(uint)size);FileClose(h);
   if(read!=size || CryptEncode(CRYPT_HASH_SHA256,bytes,key,hash)!=32)return "";
   string result="";for(int i=0;i<ArraySize(hash);i++)result+=StringFormat("%02x",hash[i]);
   return result;
}
bool LoadClockProfile() {
   ArrayResize(clock_segments,0);
   if(ClockProfileCsv=="" || StringLen(ClockProfileHash)!=64 ||
      FileSha256(ClockProfileCsv)!=ClockProfileHash)return false;
   int h=FileOpen(ClockProfileCsv,FILE_READ|FILE_CSV|FILE_ANSI,',',CP_UTF8);
   if(h==INVALID_HANDLE)return false;
   bool ok=true;
   while(!FileIsEnding(h)) {
      string begin=FileReadString(h);
      if(begin=="" && FileIsEnding(h))break;
      string end=FileReadString(h),offset=FileReadString(h);
      if(!NumericInteger(begin) || !NumericInteger(end) || !NumericInteger(offset)) {ok=false;break;}
      ATSClockSegment segment;segment.begin=StringToInteger(begin);
      segment.end=StringToInteger(end);segment.offset=StringToInteger(offset);
      int n=ArraySize(clock_segments);
      if(segment.begin<=0 || segment.end<=segment.begin || MathAbs((double)segment.offset)>14*3600 ||
         segment.offset%60!=0 || n>=1024 || (n>0 && segment.begin<clock_segments[n-1].end)) {ok=false;break;}
      ArrayResize(clock_segments,n+1);clock_segments[n]=segment;
   }
   FileClose(h);
   return ok && ArraySize(clock_segments)>0;
}
long VerifiedUTC(long broker_time) {
   long found=-1;int count=0;
   for(int i=0;i<ArraySize(clock_segments);i++) {
      long utc=broker_time-clock_segments[i].offset;
      if(utc>=clock_segments[i].begin && utc<clock_segments[i].end) {found=utc;count++;}
   }
   return count==1?found:-1;
}
bool Bars(MqlRates &rates[],int seconds,S1Bar &out[],bool full,long now) {
   ArrayResize(out,0);int count=0;long bucket=-1;
   S1Bar current;ZeroMemory(current);
   for(int i=0;i<=ArraySize(rates);i++) {
      long utc=i<ArraySize(rates)?VerifiedUTC((long)rates[i].time):now;
      if(utc<0)return false;
      bool end=i==ArraySize(rates) || utc+60>now;
      long key=utc/seconds*seconds;
      if(key!=bucket || end) {
         if(count>0 && bucket+seconds<=now && (!full || count==seconds/60)) {
            current.count=count;int n=ArraySize(out);ArrayResize(out,n+1,512);out[n]=current;
         }
         if(end)break;
         bucket=key;count=0;current.t=key;current.o=rates[i].open;
         current.h=rates[i].high;current.l=rates[i].low;
      }
      current.h=MathMax(current.h,rates[i].high);current.l=MathMin(current.l,rates[i].low);
      current.c=rates[i].close;count++;
   }
   return true;
}
bool VolumeBars(MqlRates &rates[],int seconds,S2Bar &out[],long now) {
   ArrayResize(out,0);int count=0;long bucket=-1;
   S2Bar current;ZeroMemory(current);
   for(int i=0;i<=ArraySize(rates);i++) {
      long utc=i<ArraySize(rates)?VerifiedUTC((long)rates[i].time):now;
      if(utc<0)return false;
      bool end=i==ArraySize(rates) || utc+60>now;long key=utc/seconds*seconds;
      if(key!=bucket || end) {
         if(count==seconds/60 && bucket+seconds<=now) {
            int n=ArraySize(out);ArrayResize(out,n+1,512);out[n]=current;
         }
         if(end)break;
         bucket=key;count=0;current.t=key;current.o=rates[i].open;
         current.h=rates[i].high;current.l=rates[i].low;current.v=0;
      }
      current.h=MathMax(current.h,rates[i].high);current.l=MathMin(current.l,rates[i].low);
      current.c=rates[i].close;current.v+=(double)rates[i].tick_volume;count++;
   }
   return true;
}
void Parent(int strategy,int side,long decision,double level) {
   if(!ATSParentIsNewer(decision,parents[strategy].decision))return;
   parents[strategy].side=side;parents[strategy].decision=decision;
   parents[strategy].level=level;
   parents[strategy].expires=decision+(strategy==0?7200:(strategy==1?1800:5400));
}
bool LoadSignalBars(long now) {
   MqlRates rates[];ArraySetAsSeries(rates,false);
   int n=CopyRates(BrokerSymbol,PERIOD_M1,TimeCurrent()-HistoryWarmupDays*86400,TimeCurrent(),rates);
   if(n<15000) {signal_status="BROKER_WARMUP_PENDING";return false;}
   long previous=-1;
   for(int i=0;i<n;i++) {
      long utc=VerifiedUTC((long)rates[i].time);
      if(utc<0 || utc%60!=0 || (previous>=0 && utc<=previous) ||
         !ATSFinite(rates[i].open) || !ATSFinite(rates[i].high) ||
         !ATSFinite(rates[i].low) || !ATSFinite(rates[i].close) || rates[i].low<=0 ||
         rates[i].high<MathMax(rates[i].open,rates[i].close) ||
         rates[i].low>MathMin(rates[i].open,rates[i].close)) {
         signal_status="HISTORICAL_CLOCK_OR_PRICE_INVALID";return false;
      }
      previous=utc;
   }
   if(!Bars(rates,3600,source_h1,false,now) || !Bars(rates,14400,source_h4,false,now) ||
      !Bars(rates,14400,source_h4_full,true,now) ||
      !Bars(rates,TacticalSeconds,tactical_bars,true,now) ||
      !VolumeBars(rates,3600,source_h1_full,now) || !VolumeBars(rates,900,source_m15,now))return false;
   return true;
}
void EvaluateSignals() {
   if(ClockProfileCsv=="" || ArraySize(clock_segments)==0) {signal_status="CLOCK_PROFILE_REQUIRED";return;}
   MqlTick quote;ZeroMemory(quote);
   if(!Identity() || !TerminalInfoInteger(TERMINAL_CONNECTED) || !SymbolInfoTick(BrokerSymbol,quote) ||
      quote.bid<=0 || quote.ask<quote.bid) {signal_status="FRESH_QUOTE_REQUIRED";return;}
   long now=(long)TimeGMT(),stamp=VerifiedUTC((long)quote.time);
   if(stamp<0 || now-stamp<0 || now-stamp>5) {signal_status="LIVE_CLOCK_INVALID_OR_STALE";return;}
   long boundary=now/TacticalSeconds*TacticalSeconds;
   if(boundary==last_signal_cycle || now-boundary>60)return;
   last_signal_cycle=boundary;
   if(!LoadSignalBars(now))return;
   for(int hi=ArraySize(source_h1)-1;hi>=64;hi--) {
      long decision=source_h1[hi].t+3600;if(decision<now-7200)break;
      int fi=-1;for(int j=ArraySize(source_h4)-1;j>=0;j--)if(source_h4[j].t+14400<=decision) {fi=j;break;}
      S1Signal signal;if(S1Calculate(source_h1,source_h4,hi,fi,decision,signal))Parent(0,signal.side,decision,signal.level);
   }
   for(int mi=ArraySize(source_m15)-1;mi>=20;mi--) {
      if(source_m15[mi].t+900<now-1800)break;
      S2Signal signal;if(S2Calculate(source_h1_full,source_m15,mi,signal))Parent(1,signal.side,signal.decision,signal.close);
   }
   for(int hi=ArraySize(source_h4_full)-1;hi>=40;hi--) {
      long decision=source_h4_full[hi].t+14400;if(decision<now-5400)break;
      S3Signal signal;if(S3Calculate(source_h4_full,hi,decision,signal))
         Parent(2,signal.side,decision,ATSS3RetestLevel(signal));
   }
   signal_status="NO_QUALIFYING_RETEST";
   int index=ArraySize(tactical_bars)-1;
   if(index<MathMax(14,TacticalLookback) || tactical_bars[index].t+TacticalSeconds!=boundary)return;
   for(int strategy=0;strategy<3;strategy++) {
      if((EnabledStrategyMask&(1<<strategy))==0)continue;
      ATSParent parent=parents[strategy];
      if(parent.side==0 || boundary<parent.decision+TacticalSeconds || now>parent.expires)continue;
      int side=parent.side;
      if((AllowedDirectionMask&(side==1?1:2))==0)continue;
      ATSTacticalResult tactical;
      if(!ATSTacticalCalculate(tactical_bars,index,TacticalSeconds,TacticalLookback,side,
         parent.decision,boundary,parent.level,tactical))continue;
      double atr=tactical.atr;
      if(!ATSEntryWindow(now,strategy,MinimumEntryHourUTC,MaximumEntryHourUTC,AllowedWeekdayMask))continue;
      double tick=SymbolInfoDouble(BrokerSymbol,SYMBOL_TRADE_TICK_SIZE);
      if(tick<=0)continue;
      double entry=side==1?quote.ask:quote.bid;
      double sl=ATSSnapStop(side==1?tactical.lower:tactical.upper,side,tick);
      double dist=side*(entry-sl),spread=quote.ask-quote.bid;
      if(dist<=0 || spread>1.5 || dist<4*spread || side*(quote.bid-parent.level)<-0.25*atr)continue;
      double loss1=0,margin1=0;
      ENUM_ORDER_TYPE type=side==1?ORDER_TYPE_BUY:ORDER_TYPE_SELL;
      if(!OrderCalcProfit(type,BrokerSymbol,1.0,entry,sl,loss1) || loss1>=0 ||
         !OrderCalcMargin(type,BrokerSymbol,1.0,entry,margin1) || margin1<=0)continue;
      double step=SymbolInfoDouble(BrokerSymbol,SYMBOL_VOLUME_STEP);
      double minimum=SymbolInfoDouble(BrokerSymbol,SYMBOL_VOLUME_MIN);
      double maximum=SymbolInfoDouble(BrokerSymbol,SYMBOL_VOLUME_MAX);
      if(step<=0 || minimum<=0 || maximum<minimum)continue;
      double budget=AccountInfoDouble(ACCOUNT_BALANCE)*ResearchRiskFraction;
      double lots=ATSProposalLots(budget,-loss1,EstimatedRoundTripCostPerLot,step,minimum,maximum);
      double tp=ATSSnapTarget(entry+side*TargetR*dist,side,tick);
      string strategy_id=strategy==0?Strategy1Id:(strategy==1?Strategy2Id:Strategy3Id);
      latest_proposal="{\"version\":\"ATS-SMALL-ACCOUNT-SIGNAL-V1\",\"source_strategy\":"+Quote("S"+IntegerToString(strategy+1))+
         ",\"strategy_id\":"+Quote(strategy_id)+",\"strategy_version\":"+IntegerToString(StrategyVersion)+
         ",\"preset_hash\":"+Quote(ResearchPresetHash)+
         ",\"decision_utc\":"+IntegerToString(boundary)+",\"parent_decision_utc\":"+IntegerToString(parent.decision)+
         ",\"source\":\"BROKER_M1_DERIVED_SHADOW\",\"parent_volume_provenance\":"+
         Quote(strategy==1?"TICK_VOLUME":"NOT_REQUIRED")+
         ",\"side\":"+Quote(side==1?"BUY":"SELL")+",\"entry\":"+Number(entry)+
         ",\"sl\":"+Number(sl)+",\"tp\":"+Number(tp)+",\"atr\":"+Number(atr)+
         ",\"proposed_volume\":"+(lots>=minimum?Number(lots):"null")+
         ",\"modeled_risk_cash\":"+(lots>=minimum?Number(lots*(-loss1+EstimatedRoundTripCostPerLot)):"null")+
         ",\"observed_margin_cash\":"+(lots>=minimum?Number(lots*margin1):"null")+
         ",\"proposal_status\":"+Quote(lots<minimum?"MINIMUM_LOT_EXCEEDS_BUDGET":"ATS_AUTHORIZATION_REQUIRED")+
         ",\"maximum_hold_minutes\":"+IntegerToString(MaximumHoldMinutes)+
         ",\"profit_protection\":"+Truth(EnableProfitProtection)+
         ",\"clock_profile_hash\":"+Quote(ClockProfileHash)+
         ",\"probability\":null,\"execution_authority\":\"NONE\"}";
      Store("ATS\\SmallAccount\\"+ATSAccountId+"\\signals.jsonl",latest_proposal,true);
      signal_status="PROPOSAL_ONLY";
      // The research portfolio permits one simultaneous position and uses S1/S2/S3 priority.
      break;
   }
}
#endif
