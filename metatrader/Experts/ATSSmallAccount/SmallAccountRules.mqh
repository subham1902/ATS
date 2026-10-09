#ifndef ATS_SMALL_ACCOUNT_RULES_MQH
#define ATS_SMALL_ACCOUNT_RULES_MQH

// These numerical rules compile unchanged as MQL5 and C++. The C++ fixture
// verifies this shared core, not terminal fills, clocks or full EA parity.
#include "S2Core.mqh"
#include "S1Core.mqh"
#include "S3Core.mqh"

bool ATSFinite(double value) {
#ifdef __cplusplus
   return std::isfinite(value);
#else
   return MathIsValidNumber(value);
#endif
}

struct ATSTacticalResult { double atr,lower,upper; };

bool ATSParentIsNewer(long candidate,long previous) { return candidate>previous; }

double ATSS3RetestLevel(const S3Signal &signal) {
   // The evaluated new variant retests the completed H4 CLOSE. The source
   // breakout test itself still uses the prior-ten-bar high inside S3Calculate.
   return signal.close;
}

bool ATSTacticalCalculate(S1_B,int index,int seconds,int lookback,int side,
                         long parent_decision,long decision,double level,
                         ATSTacticalResult &out) {
   if((seconds!=60 && seconds!=300) || (lookback!=1 && lookback!=3) ||
      (side!=1 && side!=-1) || index<MathMax(14,lookback) || index>=ArraySize(h) ||
      decision<parent_decision+seconds || h[index].t+seconds!=decision ||
      !ATSFinite(level) || level<=0)return false;
   for(int j=index-lookback+1;j<=index;j++) {
      if(h[j].count!=seconds/60 || h[j].t!=h[index].t-(index-j)*seconds ||
         !ATSFinite(h[j].o) || !ATSFinite(h[j].h) || !ATSFinite(h[j].l) ||
         !ATSFinite(h[j].c) || h[j].l<=0 || h[j].h<MathMax(h[j].o,h[j].c) ||
         h[j].l>MathMin(h[j].o,h[j].c))return false;
   }
   double atr=S1RMA(h,index,14);
   if(!ATSFinite(atr) || atr<=0)return false;
   bool reclaim=side*(h[index].c-level)>0 && side*(h[index].c-h[index].o)>0;
   bool touch=side==1?h[index].l<=level+0.1*atr:h[index].h>=level-0.1*atr;
   if(!reclaim || !touch)return false;
   double lower=h[index].l,upper=h[index].h;
   for(int j=index-lookback+1;j<index;j++) {
      lower=MathMin(lower,h[j].l);upper=MathMax(upper,h[j].h);
   }
   out.atr=atr;out.lower=lower-0.1*atr;out.upper=upper+0.1*atr;
   return true;
}

bool ATSEntryWindow(long utc,int strategy,int minimum_hour,int maximum_hour,int weekday_mask) {
   if(utc<=0 || strategy<0 || strategy>2 || minimum_hour<0 || maximum_hour>24 ||
      minimum_hour>=maximum_hour || weekday_mask<1 || weekday_mask>127)return false;
   int second=(int)(utc%86400),hour=second/3600;
   int weekday=(int)((utc/86400+4)%7); // Sunday=0, UTC epoch Thursday=4.
   int close_time=strategy==1?63000:72000;
   return second>=21600 && second<close_time-900 &&
          hour>=minimum_hour && hour<maximum_hour && (weekday_mask&(1<<weekday))!=0;
}

double ATSSnapStop(double price,int side,double tick) {
   if(!ATSFinite(price) || price<=0 || !ATSFinite(tick) || tick<=0 ||
      (side!=1 && side!=-1))return 0;
   return (side==1?MathFloor(price/tick+1e-9):-MathFloor(-price/tick+1e-9))*tick;
}

double ATSSnapTarget(double price,int side,double tick) {
   // Toward entry: long floor, short ceil. Never increase the modeled reward.
   return ATSSnapStop(price,side,tick);
}

double ATSProposalLots(double budget,double loss_per_lot,double cost_per_lot,
                       double step,double minimum,double maximum) {
   if(!ATSFinite(budget) || budget<=0 || !ATSFinite(loss_per_lot) || loss_per_lot<=0 ||
      !ATSFinite(cost_per_lot) || cost_per_lot<0 || !ATSFinite(step) || step<=0 ||
      !ATSFinite(minimum) || minimum<=0 || !ATSFinite(maximum) || maximum<minimum)return 0;
   double cap=MathMin(MathMin(maximum,0.10),budget/(loss_per_lot+cost_per_lot));
   double lots=MathFloor((cap+1e-12)/step)*step;
   return lots<minimum-1e-10?0:lots;
}
#endif
