#ifndef S3_CORE_MQH
#define S3_CORE_MQH
// Strategy 3: H4 long breakout, EMA30/slope confirmation. Shared numerical
// routines are kept small so a portable C++ harness can check MT5 parity.
#ifdef __cplusplus
#include <vector>
#include <cmath>
#include <algorithm>
#define S3_H const std::vector<S1Bar> &h
#define S3_ARRAY(name,n) std::vector<double> name(n)
#else
#define S3_H const S1Bar &h[]
#define S3_ARRAY(name,n) double name[]; ArrayResize(name,n)
#endif

struct S3Signal { int side; long decision; double atr, level, close; };

double S3TR(S3_H,int i) {
   double x=h[i].h-h[i].l;
   if(i>0) x=MathMax(x,MathMax(MathAbs(h[i].h-h[i-1].c),MathAbs(h[i].l-h[i-1].c)));
   return x;
}

double S3ATR(S3_H,int end) {
   const int period=14;
   if(end<period-1) return 0;
   double v=0;
   for(int i=0;i<period;i++) v+=S3TR(h,i);
   v/=period;
   for(int i=period;i<=end;i++) v=(v*(period-1)+S3TR(h,i))/period;
   return v;
}

double S3EMAAt(S3_H,int end,int span) {
   if(end<0 || end>=ArraySize(h)) return 0;
   double alpha=2.0/(span+1.0),v=h[0].c;
   for(int i=1;i<=end;i++) v=alpha*h[i].c+(1.0-alpha)*v;
   return v;
}

double S3PriorLow(S3_H,int end,int lookback) {
   if(end<lookback) return 0;
   double v=h[end-lookback].l;
   for(int i=end-lookback+1;i<end;i++) v=MathMin(v,h[i].l);
   return v;
}

bool S3Calculate(S3_H,int hi,long decision,S3Signal &s) {
   s.side=0;
   if(hi<40 || hi>=ArraySize(h) || h[hi].count!=240 ||
      h[hi].t+14400!=decision) return false;
   double top=h[hi-10].h;
   for(int i=hi-9;i<hi;i++) top=MathMax(top,h[i].h);
   double ema=S3EMAAt(h,hi,30),ema10=S3EMAAt(h,hi-10,30);
   double atr=S3ATR(h,hi);
   if(atr<=0 || h[hi].c<=top || h[hi].c<=ema || ema<=ema10) return false;
   s.side=1;s.decision=decision;s.atr=atr;s.level=top;s.close=h[hi].c;
   return true;
}
#endif
