#ifndef S2_CORE_MQH
#define S2_CORE_MQH
// Shared numerical core. C++ branch permits independent parity tests on Linux.
#ifdef __cplusplus
#include <vector>
#include <cmath>
#include <algorithm>
#define S2_H const std::vector<S2Bar> &h
#define S2_M const std::vector<S2Bar> &m
#define S2_ARRAY(name,n) std::vector<double> name(n)
template<class T> int ArraySize(const std::vector<T> &x) { return (int)x.size(); }
inline double MathAbs(double x) { return std::abs(x); }
inline double MathMin(double a,double b) { return std::min(a,b); }
inline double MathMax(double a,double b) { return std::max(a,b); }
inline double MathFloor(double x) { return std::floor(x); }
#else
#define S2_H const S2Bar &h[]
#define S2_M const S2Bar &m[]
#define S2_ARRAY(name,n) double name[]; ArrayResize(name,n)
#endif

struct S2Bar { long t; double o,h,l,c,v; };
struct S2Signal { int side; long decision; double atr,low,high,close,stretch; };

double S2Lots(double risk_budget,double loss_per_lot,double cost_per_lot,
              double margin_budget,double margin_per_lot,double step,double minlot,double maxlot)
{
   if(risk_budget<=0 || loss_per_lot<=0 || cost_per_lot<0 || margin_budget<=0 ||
      margin_per_lot<=0 || step<=0 || minlot<=0 || maxlot<minlot) return 0;
   double cap=MathMin(maxlot,MathMin(risk_budget/(loss_per_lot+cost_per_lot),margin_budget/margin_per_lot));
   double lots=MathFloor((cap+1e-12)/step)*step;
   if(lots<minlot-1e-10) return 0;
   return lots;
}

bool S2Calculate(S2_H,S2_M,int mi,S2Signal &out)
{
   out.side=0;
   if(mi<20 || mi>=ArraySize(m)) return false;
   long decision=m[mi].t+900;
   int minutes=(int)((decision%86400)/60);
   int weekday=(int)((decision/86400+4)%7); // UTC epoch was Thursday.
   if(weekday==0 || weekday==6 || minutes<750 || minutes>960) return false;
   if(m[mi].t-m[mi-4].t!=3600) return false;
   long context=(m[mi].t/3600)*3600;
   int hi=-1;
   for(int j=0;j<ArraySize(h);j++) {
      if(h[j].t+3600==context) {hi=j; break;}
      if(h[j].t+3600>context) break;
   }
   if(hi<199) return false;
   S2_ARRAY(fast,hi+1);
   double slow=0,ha=0;
   for(int j=0;j<=hi;j++) {
      double tr=h[j].h-h[j].l;
      if(j>0) tr=MathMax(tr,MathMax(MathAbs(h[j].h-h[j-1].c),MathAbs(h[j].l-h[j-1].c)));
      if(j==0) {fast[j]=h[j].c; slow=h[j].c; ha=tr;}
      else {fast[j]=(2.0/51)*h[j].c+(49.0/51)*fast[j-1];
            slow=(2.0/201)*h[j].c+(199.0/201)*slow; ha=tr/14+(13.0/14)*ha;}
   }
   double ma=0;
   for(int j=0;j<=mi;j++) {
      double tr=m[j].h-m[j].l;
      if(j>0) tr=MathMax(tr,MathMax(MathAbs(m[j].h-m[j-1].c),MathAbs(m[j].l-m[j-1].c)));
      ma=(j==0 ? tr : tr/14+(13.0/14)*ma);
   }
   if(ha<=0 || ma<=0 || m[mi].h<=m[mi].l) return false;
   double volumes[20];
   for(int j=0;j<20;j++) volumes[j]=m[mi-20+j].v;
   // Small deterministic insertion sort, identical in both languages.
   for(int j=1;j<20;j++) { double v=volumes[j]; int k=j-1;
      while(k>=0 && volumes[k]>v) {volumes[k+1]=volumes[k]; k--;}
      volumes[k+1]=v;
   }
   double median=(volumes[9]+volumes[10])/2;
   if(m[mi].v<=1.2*median) return false;
   double low=m[mi-1].l,high=m[mi-1].h;
   for(int j=mi-4;j<mi;j++) {low=MathMin(low,m[j].l); high=MathMax(high,m[j].h);}
   long day=(decision/86400)*86400;
   double upper=-1,lower=1e100; int count=0;
   for(int j=mi;j>=0;j--) {
      if(m[j].t<day+7*3600) break;
      if(m[j].t<day+8*3600) {upper=MathMax(upper,m[j].h); lower=MathMin(lower,m[j].l); count++;}
   }
   if(count!=4) return false;
   double location=(m[mi].c-m[mi].l)/(m[mi].h-m[mi].l);
   double slope=fast[hi]-fast[hi-3];
   int side=0;
   if(h[hi].c>fast[hi] && fast[hi]>slow && slope>0 && m[mi].c>upper && m[mi-1].c<=upper && location>=.7) side=1;
   if(h[hi].c<fast[hi] && fast[hi]<slow && slope<0 && m[mi].c<lower && m[mi-1].c>=lower && location<=.3) side=-1;
   if(side==0 || side*(h[hi].c-fast[hi])/ha<=1.0) return false;
   out.side=side; out.decision=decision; out.atr=ma; out.low=low; out.high=high;
   out.close=m[mi].c; out.stretch=side*(h[hi].c-fast[hi])/ha;
   return true;
}
#endif
