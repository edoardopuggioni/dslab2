for i in {1..9}; do
curl -d "entry=t$i" -X 'POST' "http://10.1.0.$i/board" &
done

